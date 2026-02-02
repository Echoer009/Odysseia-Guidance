import io
import logging
from PIL import Image
from typing import Tuple

log = logging.getLogger(__name__)


# --- 压缩策略常量 ---
NO_COMPRESSION_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10 MB (小于此值不执行迭代压缩)
MAX_IMAGE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB (硬性物理上限)
TARGET_IMAGE_SIZE_BYTES = 4 * 1024 * 1024  # 4 MB  (大于10MB的图片期望压缩到的目标大小)
MAX_IMAGE_DIMENSION = 4096  # 4096 像素 (最大尺寸)
HIGH_QUALITY = 95  # 用于10MB以下图片的保存质量
INITIAL_QUALITY = 85  # 用于10MB以上图片的初始保存质量
MIN_QUALITY = 50  # 最低可接受质量
QUALITY_STEP = 10  # 每次迭代降低的质量值


def sanitize_image(image_bytes: bytes) -> Tuple[bytes, str]:
    """
    对输入的图片字节数据进行智能预处理和压缩。
    - **如果图片 < 10MB**: 只进行必要的尺寸调整和格式统一，以高质量保存。
    - **如果图片 >= 10MB**: 执行"尽力压缩"策略，尝试将图片压缩至 4MB 以下。
    - **最终检查**: 任何情况下，处理后的图片都不能超过 15MB 的物理上限。

    内存优化：确保所有 BytesIO 缓冲区在使用后立即关闭，防止内存泄漏。
    """
    if not image_bytes:
        raise ValueError("输入的图片字节数据不能为空。")

    original_byte_size = len(image_bytes)
    log.info(f"开始处理图片，原始大小: {original_byte_size / 1024:.2f} KB。")

    input_buffer = None
    output_buffer = None

    try:
        # 使用上下文管理器确保输入缓冲区被正确关闭
        input_buffer = io.BytesIO(image_bytes)

        with Image.open(input_buffer) as img:
            # --- 1. 尺寸调整 (对所有图片都执行) ---
            if img.width > MAX_IMAGE_DIMENSION or img.height > MAX_IMAGE_DIMENSION:
                log.info(
                    f"图片尺寸 {img.size} 超过最大限制 {MAX_IMAGE_DIMENSION}px，将进行缩放。"
                )
                img.thumbnail(
                    (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS
                )
                log.info(f"图片已缩放至: {img.size}")

            # --- 2. 格式转换 (对所有图片都执行) ---
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            processed_bytes = b""

            # --- 3. 根据原始大小选择不同策略 ---
            if original_byte_size < NO_COMPRESSION_THRESHOLD_BYTES:
                # --- 策略A: 小于10MB，高质量保存 ---
                log.info("图片小于10MB，执行高质量保存。")
                output_buffer = io.BytesIO()
                img.save(output_buffer, format="WEBP", quality=HIGH_QUALITY)
                processed_bytes = output_buffer.getvalue()
                output_buffer.close()
                output_buffer = None
            else:
                # --- 策略B: 大于等于10MB，尽力压缩 ---
                log.info("图片大于等于10MB，执行迭代压缩。")
                quality = INITIAL_QUALITY
                while quality >= MIN_QUALITY:
                    output_buffer = io.BytesIO()
                    img.save(output_buffer, format="WEBP", quality=quality)
                    processed_bytes = output_buffer.getvalue()
                    output_buffer.close()
                    output_buffer = None

                    log.debug(
                        f"尝试使用质量 {quality} 进行压缩，大小为: {len(processed_bytes) / 1024:.2f} KB。"
                    )

                    if len(processed_bytes) <= NO_COMPRESSION_THRESHOLD_BYTES:
                        log.info(
                            f"压缩成功，文件大小满足目标要求。最终质量: {quality}。"
                        )
                        break

                    quality -= QUALITY_STEP
                else:
                    log.warning(
                        f"即便使用最低质量 {MIN_QUALITY}，文件大小 ({len(processed_bytes) / 1024:.2f} KB) "
                        f"仍未达到 {NO_COMPRESSION_THRESHOLD_BYTES / 1024 / 1024:.2f} MB 的目标。"
                    )

            # --- 4. 最终检查 (对所有图片都执行) ---
            if len(processed_bytes) > MAX_IMAGE_SIZE_BYTES:
                raise ValueError(
                    f"图片经过处理后大小 ({len(processed_bytes) / 1024 / 1024:.2f} MB) "
                    f"仍然超过了物理上限 {MAX_IMAGE_SIZE_BYTES / 1024 / 1024:.0f} MB。"
                )

            log.info(
                f"图片处理完成。原始大小: {original_byte_size / 1024:.2f} KB -> "
                f"处理后大小: {len(processed_bytes) / 1024:.2f} KB."
            )

            return processed_bytes, "image/webp"
    except Exception as e:
        log.error(f"图片处理过程中发生严重错误: {e}", exc_info=True)
        raise
    finally:
        # 确保所有缓冲区都被关闭
        if input_buffer is not None:
            try:
                input_buffer.close()
            except Exception:
                pass
        if output_buffer is not None:
            try:
                output_buffer.close()
            except Exception:
                pass
