import requests
import gspread
from google.oauth2.service_account import Credentials
import os
from dotenv import load_dotenv
import uuid
from moviepy.editor import ImageClip, AudioFileClip
from PIL import Image, ImageDraw, ImageFont
import textwrap
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ------------------- CONFIG -------------------
load_dotenv()
api = os.getenv("IMAGEROUTER_API_KEY")
if api and api.startswith("'") and api.endswith("'"):
    api = api[1:-1]

# ------------------- SHEET SETUP -------------------
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("resources/credentials.json", scopes=scope)
client = gspread.authorize(creds)
sheet = client.open("Quote_Access").sheet1

# ------------------- GET QUOTE -------------------
headers = sheet.row_values(1)
status_col_index = headers.index('Status') + 1
quote_col_index = headers.index('Quote') + 1
quote, target_row_index = None, None

for idx, row in enumerate(sheet.get_all_values()[1:], start=2):
    status = row[status_col_index - 1].strip().lower()
    if status != 'complete':
        quote = row[quote_col_index - 1]
        target_row_index = idx
        break

if not quote:
    print("✅ All rows are marked complete. Nothing left to process.")
    exit()

print(f"🎯 Quote selected from row {target_row_index}: {quote}")

# ------------------- GENERATE IMAGE -------------------
payload = {
    "prompt": "A stoic scene featuring [any random subject: a wise philosopher / a lone warrior / a contemplative traveler / a resilient laborer / a serene monk / a determined athlete] in [setting: ancient ruins / a misty mountain pass / a bustling medieval market / a quiet library / a stormy battlefield / a sunlit courtyard]. The atmosphere is [mood: tranquil yet powerful / melancholic but dignified / harsh yet enduring / serene with hidden strength]. The style is [art style: classical realism / cinematic chiaroscuro / neo-stoic illustration / matte painting with muted tones]. Focus on [details: weathered textures / subtle expressions of resolve / symbolic objects (like a broken sword, an old book, or a flickering lamp) / dramatic lighting]. Evoke timeless resilience and quiet intensity.",
    "model": "stabilityai/sdxl-turbo:free",
}
headers = {
    "Authorization": f"Bearer {api}",
    "Content-Type": "application/json"
}
response = requests.post("https://api.imagerouter.io/v1/openai/images/generations", json=payload, headers=headers)
data = response.json()

try:
    image_url = data['data'][0]['url']
    print(f"Image URL: {image_url}")
except (KeyError, IndexError):
    print("❌ Failed to retrieve image URL.")
    exit()

filename = f"images/{uuid.uuid4()}.jpg"
img_data = requests.get(image_url).content
with open(filename, 'wb') as handler:
    handler.write(img_data)
print(f"📥 Image saved as {filename}")

# ------------------- ADD QUOTE TO IMAGE -------------------
img = Image.open(filename).convert("RGB")
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("resources/Roboto-Italic-VariableFont_wdth,wght.ttf", size=50)
except IOError:
    font = ImageFont.truetype("arial.ttf", size=50)

w, h = img.size
wrapped_quote = textwrap.fill(quote, width=30)
text_w, text_h = draw.multiline_textbbox((0, 0), wrapped_quote, font=font)[2:]
x, y = (w - text_w) / 2, h * 0.4

draw.multiline_text((x + 2, y + 2), wrapped_quote, font=font, fill="black", align="center")
draw.multiline_text((x, y), wrapped_quote, font=font, fill="white", align="center")

quote_img_filename = "quote_image.jpg"
img.save(quote_img_filename)
print("🖼️ Quote image saved.")

# ------------------- CREATE VIDEO -------------------
audio = AudioFileClip("resources/stoic.mp3").subclip(0, 7)
clip = ImageClip(quote_img_filename).set_duration(7).resize(height=1080).set_audio(audio)
video_filename = "quote_video_with_audio.mp4"
clip.write_videofile(video_filename, fps=24)
print("🎬 Video created successfully.")

# ------------------- UPLOAD TO YOUTUBE -------------------
def authenticate_youtube():
    yt_scope = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None
    if os.path.exists("token_youtube.pickle"):
        with open("token_youtube.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file("youtube_cred.json", yt_scope)
        creds = flow.run_local_server(port=8081)
        with open("token_youtube.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build("youtube", "v3", credentials=creds)

def upload_video_to_youtube(file_path, title, description, tags, category_id=22, privacy_status="public"):
    youtube = authenticate_youtube()
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": str(category_id)
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploading... {int(status.progress() * 100)}%")
    print("✅ Upload complete!")
    print("📺 Watch here: https://www.youtube.com/watch?v=" + response["id"])

upload_video_to_youtube(
    file_path=video_filename,
    title="Stoic Quote of the Day",
    description=f"\"{quote}\"\n\nGenerated automatically using Python and AI.",
    tags=["stoicism", "motivation", "quotes", "AI video", "Marcus Aurelius"],
    category_id=22,
    privacy_status="public"
)

# ------------------- UPDATE SHEET -------------------
sheet.update_cell(target_row_index, status_col_index, 'Complete')
print(f"✅ Marked row {target_row_index} as Complete in Google Sheets.")
