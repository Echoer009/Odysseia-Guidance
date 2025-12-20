from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import yaml
from datetime import datetime


class TutorialMetadata(BaseModel):
    """
    用于校验单个教程文档元数据的 Pydantic 模型。
    确保了在数据入库前，所有元数据都符合预定义的结构和类型。
    """

    title: str = Field(..., description="教程的正式标题。")
    author: str = Field(..., description="教程的作者或贡献者名称。")
    category: str = Field(..., description="教程所属的高级类别，此为必填项。")
    tags: List[str] = Field(default_factory=list, description="与教程相关的标签列表。")
    version: Optional[str] = Field(
        None, description="教程适用的软件或库版本，例如 'SillyTavern v1.13.2'。"
    )
    difficulty: Optional[str] = Field(
        None, description="教程难度，例如 '入门', '进阶', '专家'。"
    )
    summary: Optional[str] = Field(None, description="教程核心内容的简短摘要。")
    created_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow, description="文档创建日期。"
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow, description="文档最后更新日期。"
    )

    class Config:
        # Pydantic v2 style config
        from_attributes = True


class AllTutorialsMetadata(BaseModel):
    """
    用于校验整个 metadata.yaml 文件结构的 Pydantic 模型。
    它是一个字典，键是文件名 (例如 '酒馆安装与更新&基础设置.md')，
    值是对应的 TutorialMetadata 对象。
    """

    metadata: Dict[str, TutorialMetadata]


def load_and_validate_metadata(path: str) -> Dict[str, TutorialMetadata]:
    """
    从指定的 YAML 文件路径加载元数据，并使用 Pydantic 模型进行校验。

    Args:
        path (str): metadata.yaml 文件的路径。

    Returns:
        Dict[str, TutorialMetadata]: 校验成功后，返回以文件名字符串为键，
                                     TutorialMetadata 对象为值的字典。

    Raises:
        ValidationError: 如果文件内容不符合 Pydantic 模型定义的规范。
        FileNotFoundError: 如果指定路径的文件不存在。
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # 使用 Pydantic 模型进行解析和校验
    validated_data = AllTutorialsMetadata(**data)
    return validated_data.metadata
