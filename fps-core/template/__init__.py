"""fps-core/template — プロンプトテンプレートエンジン（M6-3）"""

from .manager import TemplateManager
from .models import RenderResult, Template, TemplateVariable

__all__ = ["TemplateManager", "Template", "TemplateVariable", "RenderResult"]
