"""应用运行配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    data_dir: Path
    database_path: Path
    jiuwenswarm_data_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        project_root = Path(
            os.getenv("SUYITONG_PROJECT_ROOT", str(_default_project_root()))
        ).resolve()
        data_dir = Path(
            os.getenv("SUYITONG_DATA_DIR", str(project_root / "runtime" / "suyitong"))
        ).resolve()
        database_path = Path(
            os.getenv("SUYITONG_DATABASE_PATH", str(data_dir / "suyitong.db"))
        ).resolve()
        jiuwenswarm_data_dir = Path(
            os.getenv(
                "JIUWENSWARM_DATA_DIR",
                str(project_root / "runtime" / ".jiuwenswarm"),
            )
        ).resolve()
        return cls(
            project_root=project_root,
            data_dir=data_dir,
            database_path=database_path,
            jiuwenswarm_data_dir=jiuwenswarm_data_dir,
        )

