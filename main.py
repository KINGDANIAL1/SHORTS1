import os
import random
import time
import tempfile
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import schedule

# إعدادات Google API
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/drive.readonly']
CLIENT_SECRET_FILE = 'client_secret_696881090954-4afjsjqmmhh16fkkj2fs82dk8muijjbl.apps.googleusercontent.com.json'
SERVICE_ACCOUNT_FILE = 'scenic-kiln-451620-t8-b16dd8a13bbd.json'
TOKEN_FILE = 'token.json'  # يتم إنشاؤه بعد أول تسجيل دخول

POSTED_LOG = "posted_from_drive.txt"

# إنشاء خدمة YouTube API
def get_youtube_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        creds = flow.run_local_server(port=0)  # ✅ هذا هو التعديل المطلوب
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('youtube', 'v3', credentials=creds)

# إنشاء خدمة Google Drive
def get_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    return build('drive', 'v3', credentials=credentials)

def load_posted():
    if not os.path.exists(POSTED_LOG):
        return set()
    with open(POSTED_LOG, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_posted(filename):
    with open(POSTED_LOG, "a", encoding="utf-8") as f:
        f.write(filename + "\n")

def get_videos_from_drive(service):
    query = "mimeType contains 'video/' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    return results.get("files", [])

def download_video(service, file):
    request = service.files().get_media(fileId=file['id'])
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        downloader = MediaIoBaseDownload(tmp, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return tmp.name

def upload_video_to_youtube(youtube, file_path, title, description, tags=[]):
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22"  # People & Blogs
        },
        "status": {
            "privacyStatus": "public"
        }
    }
    media = MediaIoBaseUpload(open(file_path, 'rb'), mimetype="video/*", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print(f"✅ تم النشر: https://youtu.be/{response['id']}")

def publish_youtube_short(youtube, drive, file):
    tmp_path = download_video(drive, file)
    try:
        title = random.choice([
            "🚀 اكتشف هذا الفيديو الآن! #shorts",
            "🔥 لا تفوّت هذا المحتوى! #shorts",
            "💡 فكرة ستغيّر تفكيرك! #shorts",
        ])
        upload_video_to_youtube(youtube, tmp_path, title, "فيديو قصير من أجلك 🔥 #shorts")
        save_posted(file['name'])
    except Exception as e:
        print(f"❌ فشل النشر: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def main():
    print("🔐 تسجيل الدخول إلى YouTube و Google Drive...")
    youtube = get_youtube_service()
    drive = get_drive_service()
    posted = load_posted()

    def job():
        all_files = get_videos_from_drive(drive)
        available = [f for f in all_files if f['name'].endswith('.mp4') and f['name'] not in posted]
        if not available:
            print("🚫 لا توجد فيديوهات جديدة")
            return
        random.shuffle(available)
        publish_youtube_short(youtube, drive, available[0])

    schedule.every().day.at("09:00").do(job)
    schedule.every().day.at("15:00").do(job)

    print("⏰ السكربت يعمل تلقائيًا...")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("🛑 تم إيقاف السكربت.")

if __name__ == "__main__":
    main()
