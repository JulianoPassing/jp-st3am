# -*- coding: utf-8 -*-
# Gera icon.ico a partir do logo do site JP. Sistemas (logo_site.png)
# Fallback: gera ícone com texto JP se logo não existir
import os
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Instale Pillow: pip install Pillow")
    exit(1)

os.chdir(os.path.dirname(os.path.abspath(__file__)))

def criar_icon():
    # Usar logo do site (logo_site.png ou logo_site_2.png)
    for f in ("logo_site.png", "logo_site_2.png"):
        if os.path.exists(f):
            img = Image.open(f).convert("RGBA")
            try:
                img = img.resize((256, 256), Image.Resampling.LANCZOS)
            except AttributeError:
                img = img.resize((256, 256), Image.LANCZOS)
            img.save("icon.png")
            img.convert("RGB").save("icon.ico", format="ICO", sizes=[(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)])
            print(f"icon.png e icon.ico criados a partir de {f}!")
            return

    # Fallback: ícone gerado
    AZUL = (37, 99, 235)
    BRANCO = (255, 255, 255)
    size = 256
    img = Image.new("RGB", (size, size), AZUL)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 120)
    except:
        font = ImageFont.load_default()
    text = "JP"
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        w, h = draw.textsize(text, font=font)
    x, y = (size - w) // 2, (size - h) // 2 - 10
    draw.text((x, y), text, fill=BRANCO, font=font)
    img.save("icon.png")
    img.save("icon.ico", format="ICO", sizes=[(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)])
    print("icon.png e icon.ico criados (fallback)!")

if __name__ == "__main__":
    criar_icon()
