import requests
import gspread
from google.oauth2.service_account import Credentials
import os
from dotenv import load_dotenv
import uuid
from moviepy.editor import ImageClip
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import AudioFileClip
import textwrap

# Load environment variables
load_dotenv()
api = os.getenv("IMAGEROUTER_API_KEY")
if api and api.startswith("'") and api.endswith("'"):
    api = api[1:-1]

# Google Sheets setup
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file("resources/credentials.json", scopes=scope)
client = gspread.authorize(creds)
sheet = client.open("Quote_Access").sheet1

# Get quote from the first incomplete row
headers = sheet.row_values(1)
status_col_index = headers.index('Status') + 1
quote_col_index = headers.index('Quote') + 1
quote = None
target_row_index = None

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

# Image generation
payload = {
    "prompt": "A stoic scene featuring a lone warrior in a misty mountain pass. The atmosphere is tranquil yet powerful. The style is classical realism. Focus on subtle expressions of resolve and dramatic lighting. Evoke timeless resilience and quiet intensity.",
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

# Download image
filename = f"images/{uuid.uuid4()}.jpg"
img_data = requests.get(image_url).content
with open(filename, 'wb') as handler:
    handler.write(img_data)
print(f"📥 Image saved as {filename}")

# Overlay quote text on image
img = Image.open(filename).convert("RGB")
draw = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("resources/Roboto-Italic-VariableFont_wdth,wght.ttf", size=50)
except IOError:
    font = ImageFont.truetype("arial.ttf", size=50)
    
w, h = img.size

# Set max width (in characters) based on image width
max_chars_per_line = 30  # Adjust based on font size and image width

# Wrap the quote into lines
wrapped_quote = textwrap.fill(quote, width=max_chars_per_line)

# Now calculate position and draw as usual
text_w, text_h = draw.multiline_textbbox((0, 0), wrapped_quote, font=font)[2:]
x = (w - text_w) / 2
y = h * 0.4

# Draw shadow and main text
shadow_offset = 2
draw.multiline_text((x + shadow_offset, y + shadow_offset), wrapped_quote, font=font, fill="black", align="center")
draw.multiline_text((x, y), wrapped_quote, font=font, fill="white", align="center")

# Save the final image
quote_img_filename = "quote_image.jpg"
img.save(quote_img_filename)
print("🖼️ Quote image saved.")

# Convert image to video with 5 sec duration
audio = AudioFileClip("resources/stoic.mp3").subclip(0, 7)
clip = ImageClip(quote_img_filename).set_duration(7).resize(height=1080)
clip = clip.set_audio(audio)
clip.write_videofile("quote_video_with_audio.mp4", fps=24)
print("🎬 Video created successfully.")

# Update sheet
sheet.update_cell(target_row_index, status_col_index, 'Complete')
print(f"✅ Marked row {target_row_index} as Complete in Google Sheets.")
