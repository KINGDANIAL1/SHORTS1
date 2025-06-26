import os
import random
import time
import tempfile
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import schedule

# إعدادات Google API
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/drive.readonly']

# ملفات التكوين (يمكنك استبدالها بمتغيرات بيئية)
CLIENT_SECRET_FILE = os.getenv("CLIENT_SECRET_FILE", "client_secret.json")  # إذا تحتاج استخدامه (مش ضروري مع TOKEN_JSON فقط)
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")
TOKEN_FILE = os.getenv("TOKEN_FILE", "token.json")  # احتياطي إذا لم تستخدم TOKEN_JSON

POSTED_LOG = "posted_from_drive.txt"

def get_youtube_service():
    creds = None

    token_json = os.getenv("TOKEN_JSON")
    if token_json:
        # إنشاء ملف مؤقت من محتوى TOKEN_JSON
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as tmp_file:
            tmp_file.write(token_json)
            tmp_file.flush()
            token_path = tmp_file.name
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        os.remove(token_path)
    elif os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        raise Exception("❌ لا يوجد توكن صالح. يجب إعداد TOKEN_JSON أو عمل المصادقة محلياً أولاً.")

    return build('youtube', 'v3', credentials=creds)

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
