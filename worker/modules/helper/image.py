import zlib
import base64
from io import BytesIO
from PIL import ImageDraw, Image


class ImageHelper:


    @staticmethod
    def png_draw_rectangle(png: bytes, x: float, y: float, width: float, height: float, color: str = "red", border: int = 5) -> bytes:
        image = Image.open(BytesIO(png))
        draw = ImageDraw.Draw(image)
        draw.rectangle((x, y, x + width, y + height), outline=color, width=border)
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        return image_bytes.getvalue()


    @staticmethod
    def base64comppng_draw_rectangle(b64comppng: str, x: float, y: float, width: float, height: float, color: str = "red", border: int = 5) -> str:
        image = Image.open(BytesIO(zlib.decompress(base64.b64decode(b64comppng))))
        draw = ImageDraw.Draw(image)
        draw.rectangle((x, y, x + width, y + height), outline=color, width=border)
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        return base64.b64encode(zlib.compress(image_bytes.getvalue(), 9)).decode()
