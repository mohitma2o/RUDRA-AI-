"""Download the faster-whisper base model into the backend resource tree."""

from pathlib import Path

from huggingface_hub import snapshot_download


BACKEND_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = BACKEND_DIR / "models" / "whisper-base"


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id="Systran/faster-whisper-base",
        local_dir=str(MODEL_DIR),
    )
    print(f"Whisper base model downloaded to {MODEL_DIR}")


if __name__ == "__main__":
    main()
