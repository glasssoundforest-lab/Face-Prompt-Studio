"""fps-core/user/exceptions.py — パーソナライゼーション例外"""


class ProfileError(Exception):
    """UserProfile 操作の基底例外"""


class ProfileNotFoundError(ProfileError):
    """プロファイルファイルが存在しない"""


class ProfileSaveError(ProfileError):
    """プロファイル保存失敗"""
