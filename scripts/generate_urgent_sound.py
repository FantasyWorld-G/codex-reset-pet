"""Sequence the two selected Amitaro flustered recordings without pitch/time edits."""
from pathlib import Path
import json
import wave
ROOT = Path(__file__).resolve().parents[1]/'plugins/reset-reminder/assets/alerts'
ORDER = ['abababababa_03.wav']*3+['abababababa_04.wav']*3
GAPS = [.18,.14,.10,.075,.05,0]

def build():
    output = bytearray()
    timeline = []
    for name,gap in zip(ORDER,GAPS):
        with wave.open(str(ROOT/'sources'/name),'rb') as source:
            assert (source.getnchannels(),source.getsampwidth(),source.getframerate()) == (1,2,44100)
            pcm=source.readframes(source.getnframes())
        timeline.append({'file':name,'start':len(output)/88200,'end':(len(output)+len(pcm))/88200})
        output.extend(pcm)
        output.extend(bytes(round(gap*44100)*2))
    assert len(output)<=882000, 'Never truncate a recorded reaction'
    output.extend(bytes(882000-len(output)))
    with wave.open(str(ROOT/'urgent.wav'),'wb') as target:
        target.setparams((1,2,44100,441000,'NONE','not compressed'))
        target.writeframes(output)
    (ROOT/'timeline.json').write_text(json.dumps({'duration':10,'clips':timeline},indent=2),'utf-8')
    print('A → A → A → B → B → B, decreasing pauses; exactly 10 seconds')
if __name__=='__main__': build()
