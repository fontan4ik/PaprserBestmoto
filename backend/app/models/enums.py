from enum import Enum


class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    PARSE_MARKETPLACE = "parse_marketplace"
    IMPORT_COMMERCEML = "import_commerceml"
    MATCH_PRODUCTS = "match_products"
    EXPORT_GOOGLE = "export_google"
    FULL_BACKUP = "full_backup"

