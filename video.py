from fastapi import Depends, FastAPI, HTTPException
from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, AudioFileClip, ImageSequenceClip
from PIL import Image, ImageDraw, ImageFont

import os
import tempfile

def resize_video(input_video, output_video, width=1920, height=1080, bitrate='4000k'):
    try:
        clip = VideoFileClip(input_video)
        resized_clip = clip.resize((width, height))
        resized_clip.write_videofile(output_video, bitrate=bitrate)
        duration = resized_clip.duration
        width, height = resized_clip.size
        fps = resized_clip.fps
        clip.close()
        resized_clip.close()
        os.remove(input_video)
        return duration, f"{width}x{height}", fps
    except Exception as e:
        print(e)
        return None
    
def create_text_clip(text, duration, fontsize, fontcolor, size, font_path, start_effect, start_effect_duration, end_effect, end_effect_duration, fps):
    frames = []

    # Load the font
    font = ImageFont.truetype(font_path, fontsize)

    for i in range(int(duration * fps)):
        img = Image.new("RGBA", size, (0, 0, 0, 0))  # Create a transparent image
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((size[0] - w) / 2, (size[1] - h) / 2), text, font=font, fill=fontcolor)

        # Apply fade-in effect
        if start_effect == "fade_in" and i < start_effect_duration * fps:
            alpha = int(255 * (i / (start_effect_duration * fps)))
            img.putalpha(alpha)
        
        # Apply fade-out effect
        if end_effect == "fade_out" and i > (duration - end_effect_duration) * fps:
            alpha = int(255 * ((duration - i / fps) / end_effect_duration))
            img.putalpha(alpha)

        frames.append(img)

    temp_dir = tempfile.mkdtemp()
    frame_files = []
    for j, frame in enumerate(frames):
        frame_file = os.path.join(temp_dir, f"frame_{j:04d}.png")
        frame.save(frame_file)
        frame_files.append(frame_file)

    text_clip = ImageSequenceClip(frame_files, fps=fps)
    return text_clip
    
def render_video(clip, requests=[], fps=24):
    rendered_video = clip
    for item in requests:
        # text_clip = create_text_clip(
        #     text=item.text,
        #     duration=item.duration,
        #     fontsize=item.fontsize,
        #     fontcolor=item.fontcolor,
        #     size=clip.size,
        #     font_path=item.font or "C:/Windows/Fonts/arial.ttf",
        #     start_effect=item.start_effect,
        #     start_effect_duration=item.start_effect_duration,
        #     end_effect=item.end_effect,
        #     end_effect_duration=item.end_effect_duration,
        #     fps=fps
        # ).set_position((int(item.position.split('|')[0]), int(item.position.split('|')[1])))
        text_clip = TextClip(txt=item.text, fontsize=item.fontsize, color=item.fontcolor, font=item.font).set_duration(item.duration)
        if item.start_effect == "fade_in":
            text_clip = text_clip.fadein(item.start_effect_duration)
        if item.start_effect == "type_effect":
            text_clip = text_clip.fadein(item.start_effect_duration) ### replace into type effect
        if item.end_effect == "fade_out":
            text_clip = text_clip.fadeout(item.end_effect_duration)
        text_clip = text_clip.set_position((int(item.position.split('|')[0]), int(item.position.split('|')[1])))
        text_clip = text_clip.set_opacity(item.opacity)
        rendered_video = CompositeVideoClip([rendered_video, text_clip.set_start(item.starttime)])
    return rendered_video

def typewriter_effect(text, fontsize, color, duration, format):
    char_duration = 0.105 #duration * 0.3 / (len(text) + 1)
    clips = [
        TextClip(text[:i], fontsize=fontsize, color=color)
        .set_duration(char_duration) 
        .set_start(i * char_duration)
        .set_position(("center", "bottom"))
        for i in range(1, len(text) + 1)
    ]
    last_clip = TextClip(text, fontsize=fontsize, color=color).set_position(("center", "bottom")).set_duration(duration - char_duration * len(text)).set_start(char_duration * (len(text) + 1))
    clips.append(last_clip)
    return CompositeVideoClip(clips, size=(int(format.split("x")[0]), int(format.split("x")[1])))

def text_clip_with_style(text, format):
    text_clip = None
    if text.style == 1:
        text_clip = TextClip(txt=text.content, fontsize=120, color="white").set_duration(text.duration)
        text_clip = text_clip.set_start(text.start_time)
        text_clip = text_clip.fadein(0.3)
        text_clip = text_clip.fadeout(0.3)
        text_clip = text_clip.set_position('center')
    elif text.style == 2:
        text_clip = typewriter_effect(text=text.content, fontsize=80, color="white", duration=text.duration, format=format)
        text_clip = text_clip.set_start(text.start_time)
    return text_clip

def render_video(clip, texts, duration, format):
    rendered_video = clip
    for text in texts:
        text_clip = text_clip_with_style(text, format)
        rendered_video = CompositeVideoClip([rendered_video, text_clip])
    rendered_video.set_duration(duration)
    rendered_video.resize((int(format.split("x")[0]), int(format.split("x")[1])))
    return rendered_video