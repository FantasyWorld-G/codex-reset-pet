"""Build original nonverbal formant voices. Development-only dependency: NumPy.

No speech model, voice recording, words, or downloaded samples are used.
The desktop app plays the committed WAV assets and does not require NumPy.
"""
from pathlib import Path
import wave
import numpy as np

RATE = 24000
ROOT = Path(__file__).resolve().parents[1]/'plugins/reset-reminder/assets/sounds'
RNG = np.random.default_rng(20261029)


def voice(duration, pitch, formants, strength=.18, breath=.12, tilt=1.25, wobble=.007):
    t = np.arange(round(duration*RATE))/RATE
    progress = t/duration
    f0 = np.interp(progress, np.linspace(0, 1, len(pitch)), pitch)
    f0 *= 1+wobble*np.sin(2*np.pi*5.4*t)+.002*np.sin(2*np.pi*17.1*t)
    phase = 2*np.pi*np.cumsum(f0)/RATE
    result = np.zeros(len(t))
    # Soft glottal harmonics shaped by mouth/nasal resonances, not UI chimes.
    for harmonic in range(1, 35):
        frequency = harmonic*f0
        shaping = np.full(len(t), .025)
        for center, width, gain in formants:
            if isinstance(center, tuple):
                center = np.interp(progress, [0, 1], center)
            shaping += gain*np.exp(-.5*((frequency-center)/width)**2)
        result += shaping*np.sin(harmonic*phase+.08*harmonic)/(harmonic**tilt)
    noise = RNG.standard_normal(len(t))
    noise = np.convolve(noise, np.ones(7)/7, mode='same')
    result += breath*noise
    envelope = np.sin(np.pi*np.clip(progress, 0, 1))**.85
    # Gentle starts/ends and a low peak keep the pet from becoming intrusive.
    result *= envelope
    peak = max(np.max(np.abs(result)), 1e-9)
    return result*(strength/peak)


HUM = [(310, 180, 1), (1150, 350, .22), (2400, 550, .11)]
OPEN = [(720, 250, 1), (1750, 400, .6), (2900, 500, .25)]
ROUND = [(430, 240, 1), (1050, 320, .45), (2450, 500, .12)]
SMILE = [((650, 380), 230, 1), ((1800, 2600), 420, .9), (3200, 550, .4)]
NASAL = [(260, 90, 1), (760, 110, .16), (1300, 250, .06)]


def pause(duration):
    return np.zeros(round(duration*RATE))


def air(duration, strength=.08, center=1100):
    """Unvoiced exhalation: breath has no pitched hum underneath it."""
    count = round(duration*RATE)
    noise = RNG.standard_normal(count)
    frequencies = np.fft.rfftfreq(count, 1/RATE)
    band = np.exp(-.5*((frequencies-center)/(center*.75))**2)
    band *= 1-np.exp(-(frequencies/160)**2)
    sound = np.fft.irfft(np.fft.rfft(noise)*band, n=count)
    sound *= np.sin(np.linspace(0, np.pi, count))**1.4
    return sound*(strength/max(np.max(np.abs(sound)), 1e-9))


def build():
    ROOT.mkdir(parents=True, exist_ok=True)
    clips = {
        # Affection: two light, smiling syllables; the alternate is a rising squeak.
        'click_1': np.concatenate((voice(.16, [360, 470, 420], SMILE, .20, .12, .85),
                                  pause(.065), voice(.24, [410, 520, 440], SMILE, .22, .13, .85))),
        'click_2': voice(.46, [340, 420, 570, 440], SMILE, .21, .13, .9, .013),
        # Pout: low closed-mouth hum followed by an unvoiced dismissive puff.
        'pout': np.concatenate((voice(.38, [275, 245, 195], NASAL, .23, .035, 1.8),
                               pause(.07), air(.22, .11, 850))),
        # Pickup: a sharp intake followed by an open surprised rising/falling tone.
        'drag': np.concatenate((air(.10, .12, 2300), pause(.025),
                               voice(.41, [400, 650, 560, 365], OPEN, .24, .18, .65))),
        # Travel reward: three separated chuckles with a distinct rhythmic contour.
        'drag_happy': np.concatenate((voice(.18, [420, 560, 460], SMILE, .23, .25, .8),
                                     pause(.10), voice(.21, [460, 600, 480], OPEN, .25, .26, .8),
                                     pause(.11), voice(.34, [490, 570, 410], SMILE, .21, .28, .85))),
        'land': np.concatenate((voice(.12, [430, 330], OPEN, .21, .18, .8), pause(.075),
                               voice(.22, [355, 455, 365], SMILE, .19, .2, .9))),
        # Wake: a sleepy low-to-open yawn and a breath, not another click sound.
        'wake': np.concatenate((voice(.57, [205, 230, 340, 285],
                                     [((350, 850), 240, 1), ((900, 1550), 380, .5)],
                                     .16, .32, 1.4), pause(.065), air(.25, .07, 1000))),
    }
    # Exactly three seconds: soft breath, a barely voiced settling sigh, then air.
    clips['sleep'] = np.concatenate((pause(.10), air(.85, .055, 700), pause(.20),
                                    voice(.45, [230, 200, 170], NASAL, .065, .45, 1.9),
                                    air(1.10, .045, 600), pause(.30)))
    for name, samples in clips.items():
        pcm = np.rint(np.clip(samples, -1, 1)*32767).astype('<i2')
        with wave.open(str(ROOT/(name+'.wav')), 'wb') as output:
            output.setparams((1, 2, RATE, len(pcm), 'NONE', 'not compressed'))
            output.writeframes(pcm.tobytes())
        print(f'{name}: {len(samples)/RATE:.2f}s, peak={max(abs(samples)):.3f}')


if __name__ == '__main__':
    build()
