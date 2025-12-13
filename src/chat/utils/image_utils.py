import io
import logging
from PIL import Image
from typing import Tuple

log = logging.getLogger(__name__)


def sanitize_image(image_bytes: bytes) -> Tuple[bytes, str]:
    """
    对输入的图片字节数据进行“净化”处理，确保其格式标准。
    1. 使用Pillow打开图片。
    2. 将其转换为统一的 RGBA 模式以获得最大兼容性。
    3. 重新保存为 PNG 格式的字节流。
    这可以修复损坏的、非标准的或缺少元数据的图片文件，以兼容健壮性较差的API端点。

    Args:
        image_bytes: 原始图片的字节数据。

    Returns:
        一个元组，包含净化后的图片字节数据和新的MIME类型 ("image/png")。

    Raises:
        ValueError: 如果输入的 image_bytes 为空。
        Exception: Pillow 库在处理过程中可能抛出的任何其他异常。
    """
    if not image_bytes:
        raise ValueError("输入的图片字节数据不能为空。")

    log.info("正在对图片进行净化处理...")
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # 转换为 RGBA 模式，这是最通用的模式，可以避免很多色彩空间问题
            if img.mode != "RGBA":
                log.debug(f"图片模式为 {img.mode}，将转换为 RGBA。")
                img = img.convert("RGBA")

            # 创建一个新的 BytesIO 对象来保存转换后的图片
            output_buffer = io.BytesIO()
            # 将图片保存为 PNG 格式，PNG 兼容性好且无损
            img.save(output_buffer, format="PNG")

            sanitized_bytes = output_buffer.getvalue()

            log.info(
                f"图片净化完成。原始大小: {len(image_bytes)} bytes -> 净化后大小: {len(sanitized_bytes)} bytes."
            )

            return sanitized_bytes, "image/png"
    except Exception as e:
        log.error(f"图片净化过程中发生严重错误: {e}", exc_info=True)
        # 重新抛出异常，让调用者 (gemini_service) 捕获并处理
        raise
