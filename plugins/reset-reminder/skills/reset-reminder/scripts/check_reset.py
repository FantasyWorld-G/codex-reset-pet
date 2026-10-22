"""Read-only public fetches + local countdown/dedup state; no credential access."""
import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

CN = timezone(timedelta(hours=8))
BASE = "https://codex-reset.com"


def epoch(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.timestamp() if parsed.tzinfo else None
        except ValueError:
            pass
    return None


def stamp(value):
    return datetime.fromtimestamp(value, CN).isoformat(timespec="seconds")


def duration(seconds):
    if seconds <= 0:
        return "已到预计时间，等待账户状态刷新"
    minutes = math.ceil(seconds / 60)
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    return (f"{days}天 " if days else "") + f"{hours}小时 {minutes}分钟"


def urgency_marker(seconds):
    return (("due", "🔴") if seconds <= 0 else
            ("imminent", "🔴") if seconds <= 3600 else
            ("soon", "🟠") if seconds <= 21600 else
            ("today", "🟡") if seconds <= 86400 else ("normal", "⚪"))


def quota_display(account, now):
    """Plain-text native task label; host does not expose a text-color field."""
    windows = account.get("windows", []) if account else []
    known = [w for w in windows if w.get("resets_at") is not None]
    if not known:
        return {"name": "⚪ Codex 重置：时间待确认", "urgency": "unknown", "reset_time": None}
    nearest = min(known, key=lambda w: w["resets_at"])
    reset = nearest["resets_at"]
    seconds = reset - now
    urgency, marker = urgency_marker(seconds)
    local = datetime.fromtimestamp(reset, CN)
    short = local.strftime("%m/%d %H:%M")
    label = "最近重置" if len(known) > 1 else "重置"
    suffix = " · 待核实" if seconds <= 0 else ""
    return {"name": f"{marker} Codex {label}：{short}（北京）{suffix}",
            "reset_time": local.strftime("%Y-%m-%d %H:%M"), "timezone": "Asia/Shanghai",
            "urgency": urgency, "marker": marker, "window_key": nearest["key"]}


def card_snapshot(raw, now):
    if not isinstance(raw, dict) or not isinstance(raw.get("credits"), list):
        return None
    available = []
    for card in raw["credits"]:
        if not isinstance(card, dict):
            return None
        if card.get("status") != "available" or card.get("resetType") != "codexRateLimits":
            continue
        expiry = epoch(card.get("expiresAt"))
        if expiry is not None and expiry <= now:
            continue
        available.append({"expires_at": expiry,
                          "expires_at_shanghai": datetime.fromtimestamp(expiry, CN).strftime("%Y-%m-%d %H:%M") if expiry is not None else None,
                          "remaining_seconds": max(0, int(expiry-now)) if expiry is not None else None})
    return {"available_count": len(available), "cards": available}


def card_display(account, now):
    cards = account.get("reset_cards") if account else None
    if cards is None:
        return {"name": "⚪ 重置卡到期：时间待确认", "urgency": "unknown", "expiry_time": None}
    if not cards["cards"]:
        return {"name": "⚪ 重置卡：暂无有效卡", "urgency": "none", "expiry_time": None}
    known = [c for c in cards["cards"] if c["expires_at"] is not None and c["expires_at"] > now]
    if not known:
        return {"name": "⚪ 重置卡到期：时间待确认", "urgency": "unknown", "expiry_time": None}
    expiry = min(c["expires_at"] for c in known)
    urgency, marker = urgency_marker(expiry-now)
    local = datetime.fromtimestamp(expiry, CN)
    label = "重置卡到期" if len(known) == len(cards["cards"]) else "重置卡已知到期"
    return {"name": f"{marker} {label}：{local:%m/%d %H:%M}（北京）", "marker": marker,
            "urgency": urgency, "expiry_time": local.strftime("%Y-%m-%d %H:%M"),
            "timezone": "Asia/Shanghai", "available_count": cards["available_count"]}


def display_status(account, now):
    quota = quota_display(account, now)
    cards = card_display(account, now)
    return {**quota, "name": quota["name"] + " ｜ " + cards["name"],
            "rows": [quota["name"], cards["name"]], "reset_card": cards}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def fetch(endpoint):
    request = Request(BASE + endpoint, headers={"User-Agent": "CodexResetReminder/0.1", "Accept": "application/json"})
    with urlopen(request, timeout=20) as response:
        raw = response.read(4_000_001)
    if len(raw) > 4_000_000:
        raise ValueError("response too large")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("unexpected response schema")
    return data


def account_snapshot(envelope, now):
    captured = epoch(envelope.get("captured_at"))
    if captured is None or not -60 <= now - captured <= 600:
        raise ValueError("账户快照超过10分钟或时间无效，请重新读取")
    usage = envelope.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("账户数据格式无效")
    identity = usage.get("accountId")
    if not identity:
        raise ValueError("账户标识缺失，无法安全隔离提醒状态")
    account_key = hashlib.sha256(str(identity).encode()).hexdigest()[:20]
    buckets = usage.get("rateLimitsByLimitId")
    if not isinstance(buckets, dict) or not buckets:
        legacy = usage.get("rateLimits")
        buckets = {legacy.get("limitId") or "codex": legacy} if isinstance(legacy, dict) else {}
    windows = []
    for bucket_id, bucket in buckets.items():
        if not isinstance(bucket, dict):
            continue
        for slot in ("primary", "secondary"):
            item = bucket.get(slot)
            if not isinstance(item, dict):
                continue
            reset = epoch(item.get("resetsAt"))
            used = item.get("usedPercent")
            valid_used = isinstance(used, (int, float)) and not isinstance(used, bool) and math.isfinite(used)
            remaining = max(0, min(100, 100 - used)) if valid_used else None
            seconds = max(0, int(reset - now)) if reset is not None else None
            windows.append({"key": f"{account_key}:{bucket_id}:{slot}", "bucket": str(bucket_id),
                            "name": bucket.get("limitName") or str(bucket_id), "window": slot,
                            "window_minutes": item.get("windowDurationMins"), "remaining_percent": remaining,
                            "resets_at": reset, "resets_at_shanghai": stamp(reset) if reset is not None else None,
                            "remaining_seconds": seconds, "remaining": duration(seconds) if seconds is not None else "重置时间未知"})
    return {"captured_at": envelope["captured_at"], "windows": windows,
            "reset_cards": card_snapshot(usage.get("rateLimitResetCredits"), now)}


def community_snapshot(feed, timeline, now):
    for data, time_key, list_key in ((feed, "fetched_at", "tweets"), (timeline, "updated_at", "events")):
        fetched = epoch(data.get(time_key))
        if data.get("stale") is True or fetched is None or not -300 <= now - fetched <= 7200:
            raise ValueError("社区数据过期或缺少采集时间")
        if not isinstance(data.get(list_key), list):
            raise ValueError("社区接口结构变化")
    events = {}
    for raw in feed["tweets"]:
        if not isinstance(raw, dict):
            raise ValueError("社区动态结构变化")
        if raw.get("kind") in ("signal", "candidate"):
            events[str(raw.get("id"))] = {"id": str(raw.get("id")), "status": "signal" if raw["kind"] == "signal" else "pending",
                                            "text": raw.get("text", ""), "url": raw.get("url"), "at": raw.get("at")}
    for raw in timeline["events"]:
        if not isinstance(raw, dict):
            raise ValueError("社区时间轴结构变化")
        if raw.get("type") not in ("reset", "credits"):
            continue
        ident = str(raw.get("id"))
        confirmed = raw.get("confirmed") is True
        status = "banked" if confirmed and raw.get("banked_grant") is True else "community_confirmed" if confirmed else "pending"
        if ident not in events or confirmed:
            events[ident] = {"id": ident, "status": status, "text": raw.get("summary", ""), "url": raw.get("url"), "at": raw.get("announced_at")}
    clean = []
    for event in events.values():
        if event["id"] in ("None", "") or epoch(event["at"]) is None:
            continue
        if not isinstance(event["url"], str) or not event["url"].startswith("https://x.com/thsottiaux/status/"):
            continue
        # Never derive a deadline from natural-language hints or forecast percentages.
        event["countdown"] = None
        clean.append(event)
    clean.sort(key=lambda e: epoch(e["at"]), reverse=True)
    return {"fetched_at": feed["fetched_at"], "source": BASE + "/zh/tibo", "events": clean}


def evaluate(previous, account, community, errors, now):
    state = json.loads(json.dumps(previous))
    state.setdefault("windows", {})
    state.setdefault("notified", [])
    state.setdefault("events", {})
    state.setdefault("failures", {})
    seen = set(state["notified"])
    alerts = []
    for source, snapshot in (("account", account), ("community", community)):
        failures = state["failures"].get(source, 0)
        if source in errors:
            failures += 1
            state["failures"][source] = failures
            if failures == 3:
                alerts.append({"type": "source_error", "source": source, "message": errors[source]})
        elif snapshot is not None:
            if failures >= 3:
                alerts.append({"type": "source_recovered", "source": source})
            state["failures"][source] = 0
    if account is not None:
        for current in account["windows"]:
            key = current["key"]
            old = state["windows"].get(key)
            reset = current["resets_at"]
            if reset is not None:
                seconds = reset - now
                threshold = 0 if seconds <= 0 else 3600 if seconds <= 3600 else 21600 if seconds <= 21600 else None
                token = f"{key}:{reset}:{threshold}"
                if threshold is not None and token not in seen:
                    seen.add(token)
                    if old is not None:
                        alerts.append({"type": "account_due" if threshold == 0 else "account_soon", "window": current})
                if old and old.get("resets_at") is not None and reset > old["resets_at"] and reset > now:
                    alerts.append({"type": "account_window_changed", "window": current,
                                   "message": "账户重置时间已更新，请以当前剩余额度为准；不能据此认定为Tibo重置。"})
            state["windows"][key] = current
    if community is not None:
        initialized = state.get("community_initialized", False)
        for event in community["events"]:
            fingerprint = hashlib.sha256((event["status"] + str(event["text"])).encode()).hexdigest()
            old = state["events"].get(event["id"])
            if initialized and old != fingerprint and -300 <= now - epoch(event["at"]) <= 3 * 86400:
                alerts.append({"type": "tibo_update", "event": event})
            state["events"][event["id"]] = fingerprint
        state["community_initialized"] = True
    state["notified"] = sorted(seen)[-2000:]
    state["checked_at"] = stamp(now)
    return state, alerts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--usage")
    parser.add_argument("--commit", action="store_true", help="Commit notification baseline; omit for interactive queries")
    parser.add_argument("--fixtures", help="Offline test directory containing feed.json and timeline.json")
    args = parser.parse_args()
    now = datetime.now(timezone.utc).timestamp()
    state_path = Path(args.state)
    # Refuse corrupt state instead of silently losing notification history.
    previous = read_json(state_path) if state_path.exists() else {}
    errors = {}
    account = community = None
    try:
        if not args.usage:
            raise ValueError("本轮账户状态不可用，未读取缓存")
        account = account_snapshot(read_json(args.usage), now)
    except (OSError, ValueError, TypeError) as exc:
        errors["account"] = str(exc)
    try:
        if args.fixtures:
            feed = read_json(Path(args.fixtures) / "feed.json")
            timeline = read_json(Path(args.fixtures) / "timeline.json")
        else:
            feed, timeline = fetch("/api/feed"), fetch("/api/timeline")
        community = community_snapshot(feed, timeline, now)
    except (OSError, ValueError, TypeError) as exc:
        errors["community"] = str(exc)
    state, alerts = evaluate(previous, account, community, errors, now)
    if args.commit:
        write_json(state_path, state)
    if community:
        community["events"] = community["events"][:6]
    print(json.dumps({"checked_at": stamp(now), "display": display_status(account, now), "account": account, "community": community,
                      "errors": errors, "alerts": alerts, "state_committed": args.commit}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
