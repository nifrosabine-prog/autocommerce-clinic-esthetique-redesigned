from PIL import Image, ImageDraw, ImageFont

image = Image.new('RGB', (1200, 800), '#e8eef5')
draw = ImageDraw.Draw(image)
font = ImageFont.load_default()
draw.rectangle((40, 40, 1160, 760), outline='#1f4e79', width=5)
draw.text((90, 120), 'AUTOCLINIQUE — PHOTO QA / FAKE', fill='#17365d', font=font)
draw.text((90, 180), 'Patient recette : Ines Gharbi', fill='#17365d', font=font)
draw.text((90, 240), 'Type : AVANT INTERVENTION', fill='#17365d', font=font)
draw.text((90, 300), 'Image fictive — ne pas utiliser en production', fill='#b00020', font=font)
draw.text((90, 360), 'Test de validation du dossier médical', fill='#17365d', font=font)
image.save('/home/ubuntu/work/autoclinique/qa_photo_avant_fake.jpg', quality=90)
