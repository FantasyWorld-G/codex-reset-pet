"""Render the actual desktop urgent poses into a 10-second GIF and MP4 preview."""
from pathlib import Path
import sys, subprocess, shutil
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugins/reset-reminder/skills/reset-reminder/scripts'))
from animation_state import animation_pose

def build(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    assets=ROOT/'plugins/reset-reminder/assets'
    sheet=Image.open(assets/'maid-urgent-sprites.png').convert('RGBA')
    cell=sheet.width//3
    sprites=[sheet.crop((i*cell,0,(i+1)*cell,sheet.height)).resize((320,320),Image.Resampling.LANCZOS) for i in range(3)]
    frames=[]
    for index in range(200):
        elapsed=index/20
        frame,angle,offset,label=animation_pose('urgent',elapsed)
        character=Image.new('RGBA',(400,400))
        character.alpha_composite(sprites[frame-6],(40,40))
        character=character.rotate(angle,resample=Image.Resampling.BICUBIC)
        canvas=Image.new('RGB',(400,440),'#182735')
        canvas.paste(character,(0,round(offset)),character)
        draw=ImageDraw.Draw(canvas)
        font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
        draw.text((200,412),label,anchor='mm',font=font,fill='white')
        frames.append(canvas)
    frames[0].save(destination/'urgent-progressive.gif',save_all=True,append_images=frames[1:],duration=50,loop=0,optimize=False)
    frames[110].save(destination/'urgent-preview-still.png')
    shutil.copy2(assets/'alerts/urgent.wav',destination/'urgent-progressive.wav')
    import imageio_ffmpeg
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-pix_fmt','rgb24','-s','400x440','-r','20','-i','-',
             '-i',str(assets/'alerts/urgent.wav'),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-t','10','-movflags','+faststart',str(destination/'urgent-progressive.mp4')]
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    _,err=process.communicate(b''.join(frame.tobytes() for frame in frames))
    if process.returncode: raise RuntimeError(err.decode('utf-8',errors='replace'))
    print('Rendered 200 frames, 20 fps, ten-second GIF and synchronized MP4')
if __name__=='__main__':build(sys.argv[1])
