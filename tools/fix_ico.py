import os
from PIL import Image

# 1. Caminho do teu ficheiro original (Usa uma cópia da tua imagem em .PNG ou .JPG)
caminho_imagem_original = r"C:\Users\MIKE\Desktop\APPS\TIMER\app.ico"  # Podes apontar para o teu PNG original se tiveres!
caminho_ico_final = r"C:\Users\MIKE\Desktop\APPS\TIMER\app.ico"

try:
    # Abre o ficheiro e força a conversão para RGBA (Canal Alfa Transparente Verdadeiro)
    img = Image.open(caminho_imagem_original).convert("RGBA")

    # Embala as 4 sub-resoluções que o Windows usa para a Barra, Ecrã e Inno Setup
    tamanhos_obrigatorios = [(16, 16), (32, 32), (48, 48), (256, 256)]
    img.save(caminho_ico_final, format="ICO", sizes=tamanhos_obrigatorios)
    print("[Sucesso] O app.ico foi purificado e as camadas foram cravadas com sucesso!")
except Exception as e:
    print(f"Erro ao converter: {e}")