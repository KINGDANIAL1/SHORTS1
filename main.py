import os
import random
import time
import tempfile
import schedule
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

# إعدادات Google API
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/drive.readonly']
TOKEN_FILE = 'token.json'
POSTED_LOG = "posted_from_drive.txt"

# عناوين قوية لجذب المشاهد
TITLES = [
    "❌ أكبر خطأ ترتكبه كل يوم! ",
    "🚀 كيف تبدأ من الصفر؟ شاهد هذا",
    "🔥 هذه الجملة غيرت حياة الآلاف!",
    "💡 سر النجاح في دقيقة!",
    "📉 لماذا يفشل معظم الناس؟",
    "🧠 تمرين ذهني يغير كل شيء!"
]

# وسوم ذكية تؤثر على الخوارزمية
DEFAULT_HASHTAGS = [
     "#تعلم", "#تحفيز", "#ريادة_أعمال", "#نصائح", "#ابدأ_الآن"
]

# وصف احترافي للفيديو
DESCRIPTION = """
🔥 فيديو قصير مليء بالإلهام!
📌 لا تنسَ الاشتراك لمزيد من الفيديوهات التحفيزية.

#ريادة_أعمال #تحفيز #ابدأ
"""

# إنشاء خدمة YouTube API
def get_youtube_service():
    creds = None
    token_json = os.getenv("TOKEN_JSON")
    if token_json:
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as tmp_file:
            tmp_file.write(token_json)
            tmp_file.flush()
            tmp_path = tmp_file.name
        creds = Credentials.from_authorized_user_file(tmp_path, SCOPES)
        os.remove(tmp_path)
    else:
        raise Exception("❌ يرجى توفير TOKEN_JSON كمتغير بيئي")
    return build('youtube', 'v3', credentials=creds)

# إنشاء خدمة Google Drive باستخدام حساب خدمة من متغير بيئي
def get_drive_service():
    service_account_json = os.getenv("SERVICE_ACCOUNT_JSON")
    if not service_account_json:
        raise Exception("❌ يرجى ضبط متغير SERVICE_ACCOUNT_JSON بمحتوى ملف حساب الخدمة.")

    with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as tmp_file:
        tmp_file.write(service_account_json)
        tmp_file.flush()
        tmp_path = tmp_file.name

    credentials = service_account.Credentials.from_service_account_file(tmp_path, scopes=SCOPES)
    os.remove(tmp_path)
    return build('drive', 'v3', credentials=credentials)

# تحميل الملفات المنشورة
def load_posted():
    if not os.path.exists(POSTED_LOG):
        return set()
    with open(POSTED_LOG, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

# حفظ الملفات المنشورة
def save_posted(filename):
    with open(POSTED_LOG, "a", encoding="utf-8") as f:
        f.write(filename + "\n")

# جلب الفيديوهات من Google Drive
def get_videos_from_drive(service):
    query = "mimeType contains 'video/' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    return results.get("files", [])

# تنزيل الفيديو محلياً
def download_video(service, file):
    request = service.files().get_media(fileId=file['id'])
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        downloader = MediaIoBaseDownload(tmp, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return tmp.name

# رفع الفيديو إلى YouTube كـ Shorts
def upload_video_to_youtube(youtube, file_path, title, description, tags=[]):
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": [tag.strip("#") for tag in tags],
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    media = MediaIoBaseUpload(open(file_path, 'rb'), mimetype="video/*", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print(f"✅ تم النشر على يوتيوب: https://youtu.be/{response['id']}")

# عملية النشر الكاملة
def publish_youtube_short(youtube, drive, file):
    tmp_path = download_video(drive, file)
    try:
        title = random.choice(TITLES)
        upload_video_to_youtube(youtube, tmp_path, title, DESCRIPTION, DEFAULT_HASHTAGS)
        save_posted(file['name'])
    except Exception as e:
        print(f"❌ فشل النشر: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# مهمة مجدولة يوميًا
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

    schedule.every().day.at("10:00").do(job)
    schedule.every().day.at("14:00").do(job)
    schedule.every().day.at("18:00").do(job)
    schedule.every().day.at("21:00").do(job)

    print("⏰ السكربت يعمل تلقائيًا...")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("🛑 تم إيقاف السكربت.")

if __name__ == "__main__":
    main()
