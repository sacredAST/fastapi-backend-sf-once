from fastapi import Depends, FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi_utils.tasks import repeat_every
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, afx
from database import UploadVideo, DownloadFile, UploadBackgroundMusic, RenderText, BackgroundMusic, ProcessVideoRequest, get_db, SessionLocal
from video import resize_video, render_video
from datetime import datetime, timedelta
import os
import uuid
import paramiko
import time

os.environ["IMAGEMAGICK_BINARY"] = "C:/Program Files/ImageMagick-7.1.1-Q16-HDRI/magick.exe"
os.environ["FFMPEG_BINARY"] = "E:\\Projects\\AI\\Andreas\\ffmpeg-master-latest-win64-lgpl-shared\\bin\\magick.exe"

app = FastAPI()

app.mount("/static", StaticFiles(directory="public/static"), name="static")

# Set all CORS enabled origins
origins = [
    "http://localhost:3001",
    "http://localhost:8000",
    "http://yourdomain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIRECTORY = "uploads"
PROCESSED_DIRECTORY = "processed"
MUSIC_DIRECTORY = os.path.join(UPLOAD_DIRECTORY, "musics")
IMAGE_DIRECTORY = os.path.join(UPLOAD_DIRECTORY, "images")

# ftp_host = "access972093172.webspace-data.io"
# ftp_port = 22
# ftp_username = "acc837530331"
# ftp_password = "MYCTS<c{c§U{}vB,xE222kF@_m)T(GgTmj>fbG~qG"

formats = {
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
    "4:3": (1440, 1080)
}

if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

if not os.path.exists(MUSIC_DIRECTORY):
    os.makedirs(MUSIC_DIRECTORY)

if not os.path.exists(IMAGE_DIRECTORY):
    os.makedirs(IMAGE_DIRECTORY)

if not os.path.exists(PROCESSED_DIRECTORY):
    os.makedirs(PROCESSED_DIRECTORY)

@app.on_event("startup")
@repeat_every(seconds=86400)  # Run daily for deleting video last 30 days
def remove_old_files(db: Session = SessionLocal()):
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    old_videos = db.query(DownloadFile).filter(DownloadFile.used_at < thirty_days_ago).all()
    for video in old_videos:
        try:
            os.remove(video.file_path)
        except FileNotFoundError:
            pass
        db.delete(video)
    db.commit()

# def connect_sftp():
#     try:
#         transport = paramiko.Transport((ftp_host, ftp_port))
#         transport.connect(username=ftp_username, password=ftp_password)
#         sftp = paramiko.SFTPClient.from_transport(transport)
#         print("SFTP connection established.")
#         return sftp
#     except Exception as e:
#         print(f"Error connecting to SFTP server: {e}")
#         return None
    
# Serve the index.html file from the React build directory
@app.get("/", response_class=HTMLResponse)
def serve_react_app(request: Request):
    with open("public/index.html") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.post("/upload/")
async def uploads_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Only .mp4 files are allowed.")
    try:
        file_uuid = str(uuid.uuid4())
        file_extension = file.filename.split('.')[-1]
        new_filename = f"{file_uuid}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIRECTORY, new_filename)

        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        output_filename = f"{str(uuid.uuid4())}.{file_extension}"
        output_filepath = os.path.join(UPLOAD_DIRECTORY, output_filename)
        print(file_path)
        duration, resolution, fps  = resize_video(file_path, output_filepath)
        video = UploadVideo(
            filename=output_filename,
            realname=file.filename,
            file_path=output_filepath,
            duration=duration,
            resolution=resolution,
            fps=fps,
            created_at=datetime.utcnow()
        )
        db.add(video)
        db.commit()
        db.refresh(video)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Error occurs.")

    return JSONResponse(content={"filename": output_filename}, status_code=200)

@app.get("/uploads/{filename}")
async def get_file(filename: str):
    file_path = os.path.join(UPLOAD_DIRECTORY, filename)
    return FileResponse(file_path)

@app.get("/processed/{filename}")
async def get_file(filename: str):
    file_path = os.path.join(PROCESSED_DIRECTORY, filename)
    return FileResponse(file_path)

@app.post("/upload_music/")
async def upload_music(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not (file.filename.endswith(".mp3") or file.filename.endswith(".wma") or file.filename.endswith(".wav")):
        raise HTTPException(status_code=400, detail="Only .mp3, .wav and .wma files are allowed.")
    try:
        file_uuid = str(uuid.uuid4())
        file_extension = file.filename.split('.')[-1]
        new_filename = f"{file_uuid}.{file_extension}"
        file_path = os.path.join(MUSIC_DIRECTORY, new_filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        music = UploadBackgroundMusic(filename=new_filename, file_path=file_path, created_at=datetime.utcnow())
        db.add(music)
        db.commit()
        db.refresh(music)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Error occurs.")

    return JSONResponse(content={"filename": new_filename}, status_code=200)

@app.get("/videos/")
async def get_videos(db: Session = Depends(get_db)):
    videos = db.query(UploadVideo).all()
    if not videos:
        raise HTTPException(status_code=404, detail="No videos found")
    return videos

@app.post("/render")
async def process_video(request: ProcessVideoRequest, db: Session = Depends(get_db)):
    video_clips = []
    for item in request.render_video:
        video_record = db.query(UploadVideo).filter(UploadVideo.filename == item).first()
        if not video_record:
            raise HTTPException(status_code=404, detail=f"Video file {item} not found")
        video_record.used_at = datetime.utcnow()
        clip = VideoFileClip(video_record.file_path)
        video_clips.append(clip)
        db.commit()
    merged_clip = concatenate_videoclips(video_clips)
    rendered_video = render_video(merged_clip, request.render_texts, merged_clip.fps)
    for music_item in request.background_music:
        music_record = db.query(UploadBackgroundMusic).filter(UploadBackgroundMusic.filename == music_item.filename).first()
        if not music_record:
            raise HTTPException(status_code=404, detail=f"Music file {music_item.filename} not found")
        if music_item.duration == None:
            audio_clip = AudioFileClip(music_record.file_path).set_start(music_item.start)
        else:
            audio_clip = AudioFileClip(music_record.file_path).subclip(music_item.start, music_item.start + music_item.duration)
        
        if music_item.loop:
            audio_clip = audio_clip.loop()
        rendered_video = rendered_video.set_audio(audio_clip)

    output_filename = f"{str(uuid.uuid4())}.mp4"
    output_path = os.path.join(PROCESSED_DIRECTORY, output_filename)
    rendered_video.write_videofile(
        output_path,
        threads=16
    )
    return JSONResponse(content={"output_filename": output_path}, status_code=200)

    # sftp = connect_sftp()
    # if sftp is None:
    #     return JSONResponse(content={"Error"}, status_code=400)
    # remote_input_folder = "/Eingang"
    # try:
    #     with open('./ftp-file-list.txt', 'w') as file:
    #         while True:
    #             print(f"Listing files in remote folder: {remote_input_folder}")
    #             files = sftp.listdir(remote_input_folder)
    #             if not files:
    #                 print("No files found. Waiting for new files...")
    #                 time.sleep(5)  # Warte 5 Sekunden, bevor erneut überprüft wird
    #                 continue
    #             print(f"Files found: {files}")
    #             for file in files:
    #                 if any(file.endswith(ext) for ext in [".mp4"]):
    #                     remote_path = os.path.join(remote_input_folder, file).replace("\\", "/")
    #                     local_path = os.path.join(UPLOAD_DIRECTORY, file).replace("\\", "/")
    #                     print(f"Downloading {remote_path} to {local_path}")
    #                     try:
    #                         sftp.get(remote_path, local_path)
    #                         print(f"Downloaded {remote_path} successfully.")
    #                         file.write(local_path)
    #                     except Exception as e:
    #                         print(f"Error processing {remote_path}: {e}")
    #                         continue
    # except Exception as e:
    #     print(f"Error listing files in remote folder: {e}")
    # finally:
    #     sftp.close()
    #     file.close()
    # return JSONResponse(content={"output_filename": "111"}, status_code=200)
@app.post("/api/uploads")
async def uploads_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        if file.filename.endswith(".mp4"):
            output_filename = f"{str(uuid.uuid4())}.mp4"
            output_filepath = os.path.join(UPLOAD_DIRECTORY, output_filename)
            print(file_path)
            duration, resolution, fps  = resize_video(file_path, output_filepath)
        else:
            output_filepath = os.path.join(UPLOAD_DIRECTORY, file.filename)
            print(file_path)

    except Exception as e:
        raise HTTPException(status_code=400, detail="Error occurs.")
    return JSONResponse(content={"filename": output_filepath}, status_code=200)

def find_download_video(file):
    file_path = os.path.join(UPLOAD_DIRECTORY, file)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "success": True,
        "filename": file_path
    }

def find_download_music(file):
    file_path = os.path.join(MUSIC_DIRECTORY, file)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "success": True,
        "filename": ""
    }

def find_download_image(file):
    file_path = os.path.join(IMAGE_DIRECTORY, file)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "success": True,
        "filename": ""
    }

@app.post("/api/render")
async def render_video_real_time(request: ProcessVideoRequest, db: Session = Depends(get_db)):
    video_clips = []
    # Video Download from given file name.
    for video in request.videos:
        # old_videos = db.query(DownloadFile).filter(DownloadFile.realname == video).all()
        # if old_videos.count() > 0:
        try:
            video_clips.append(VideoFileClip(video))
        except Exception as e:
            return JSONResponse(content={"message": "Couldn't find video", "error": True}, status_code=400)
        # else:
        #     response = find_download_video(video)
        #     if response["success"]:
        #         downloaded_video = DownloadFile(
        #             path=response["filename"],
        #             realname=video,
        #             created_at=datetime.utcnow()
        #         )
        #         db.add(downloaded_video)
        #         db.commit()
        #         db.refresh(downloaded_video)
        #         video_clips.append(VideoFileClip(response["filename"]))
        #     elif response["success"] is not True:
        #         return JSONResponse(content={"output_filename": "", "error": True}, status_code=400)

    print(f">>>>>>>>>>>>> Video Clips Num : {len(video_clips)} <<<<<<<<<<<<<<")

    # Music Download from given file name.
    # old_music = db.query(DownloadFile).filter(DownloadFile.realname == request.music).all()
    # audio_clip = None
    # if old_music.count() > 0:
    #     audio_clip = AudioFileClip(old_music[0].path)
    # else:
    #     response = find_download_music(request.music)
    #     if response["success"]:
    #         downloaded_music = DownloadFile(
    #             path=response["filename"],
    #             realname=request.music,
    #             created_at=datetime.utcnow()
    #         )
    #         db.add(downloaded_music)
    #         db.commit()
    #         db.refresh(downloaded_music)
    #         audio_clip = AudioFileClip(response["filename"])
    #     elif response["success"] is not True:
    #         return JSONResponse(content={"output_filename": "", "error": True}, status_code=400)
    # print(f">>>>>>>>>>>>> Music Loaded <<<<<<<<<<<<<<")
    
    merged_clip = concatenate_videoclips(video_clips) 
    merged_clip_with_image = [merged_clip]
    for image in request.images:
        try:
            image_clip = ImageClip(image.file).set_start(image.start_time)
            image_clip = image_clip.set_duration(image.duration)
            merged_clip_with_image.append(image_clip)
        except Exception as e:
            return JSONResponse(content={"message": "Couldn't find image", "error": True}, status_code=400)
        # old_images = db.query(DownloadFile).filter(DownloadFile.realname == image).all()
        # if old_images.count() > 0:
        #     image_clip = ImageClip(old_images[0].path).set_start(image.start_time)
        #     image_clip = image_clip.set_duration(image.duration)
        #     merged_clip_with_image.append(image_clip)
        # else:
        #     response = find_download_image(image)
        #     if response["success"]:
        #         downloaded_image = DownloadFile(
        #             path=response["filename"],
        #             realname=image,
        #             created_at=datetime.utcnow()
        #         )
        #         db.add(downloaded_image)
        #         db.commit()
        #         db.refresh(downloaded_image)
        #         image_clip = ImageClip(response["filename"]).set_start(image.start_time)
        #         image_clip = image_clip.set_duration(image.duration)
        #         merged_clip_with_image.append(image_clip)
        #     elif response["success"] is not True:
        #         return JSONResponse(content={"output_filename": "", "error": True}, status_code=400)
    print(f">>>>>>>>>>>>> Image Clips Num : {len(merged_clip_with_image) - 1} <<<<<<<<<<<<<<")

    merged_result = CompositeVideoClip(merged_clip_with_image)
    rendered_video = render_video(merged_result, request.text, request.duration, request.format)
    if request.music != "":
        audio_clip = AudioFileClip(request.music)
        looped_audio = afx.audio_loop(audio_clip, duration=request.duration)
        rendered_video = rendered_video.set_audio(looped_audio)
        try:
            audio_clip = AudioFileClip(request.music)
            print(f">>>>>>>>>>>>> Music Loaded <<<<<<<<<<<<<<")
        except Exception as e:
            return JSONResponse(content={"message": "Couldn't find music", "error": True}, status_code=400)
    output_filename = f"{str(uuid.uuid4())}.mp4"
    output_path = os.path.join(PROCESSED_DIRECTORY, output_filename)
    rendered_video.write_videofile(
        output_path,
        threads=64
    )
    return JSONResponse(content={"output_filename": output_path, "error": False}, status_code=200)

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(PROCESSED_DIRECTORY, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=filename, media_type='video/mp4')
