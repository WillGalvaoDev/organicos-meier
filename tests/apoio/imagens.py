"""Imagens geradas em memória para os testes de avatar (E02-09)."""

from io import BytesIO

from PIL import Image

LIMITE_DE_BYTES = 2 * 1024 * 1024


def png(largura: int = 100, altura: int = 100) -> bytes:
    saida = BytesIO()
    Image.new("RGB", (largura, altura), "green").save(saida, "PNG")
    return saida.getvalue()


def png_com_texto_de_metadados() -> bytes:
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text("Author", "Fulana de Tal")
    saida = BytesIO()
    Image.new("RGB", (30, 30), "blue").save(saida, "PNG", pnginfo=info)
    return saida.getvalue()


def jpeg_com_gps() -> bytes:
    """JPEG com EXIF contendo fabricante e coordenadas GPS."""
    imagem = Image.new("RGB", (60, 40), "red")
    exif = Image.Exif()
    exif[0x010F] = "FabricanteTeste"
    gps = exif.get_ifd(0x8825)
    gps[1] = "S"
    gps[2] = (22.0, 54.0, 30.0)
    gps[3] = "W"
    gps[4] = (43.0, 16.0, 40.0)
    saida = BytesIO()
    imagem.save(saida, "JPEG", exif=exif)
    return saida.getvalue()


def webp() -> bytes:
    saida = BytesIO()
    Image.new("RGB", (64, 64), "yellow").save(saida, "WEBP")
    return saida.getvalue()


def gif() -> bytes:
    saida = BytesIO()
    Image.new("P", (20, 20)).save(saida, "GIF")
    return saida.getvalue()


def png_com_mais_de_2mb() -> bytes:
    """PNG válido seguido de bytes extras até ter 2 MB + 1 byte."""
    base = png()
    return base + b"\0" * (LIMITE_DE_BYTES + 1 - len(base))
