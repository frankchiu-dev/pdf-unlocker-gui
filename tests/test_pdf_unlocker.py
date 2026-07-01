from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pikepdf


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "pdf_unlocker.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pdf_unlocker", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_blank_pdf(path: Path) -> None:
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(144, 144))
    pdf.save(path)


def make_encrypted_pdf(src: Path, dest: Path, user: str = "", restrict: bool = False) -> None:
    allow = pikepdf.Permissions(
        accessibility=True,
        extract=not restrict,
        modify_annotation=not restrict,
        modify_assembly=not restrict,
        modify_form=not restrict,
        modify_other=not restrict,
        print_lowres=not restrict,
        print_highres=not restrict,
    )
    with pikepdf.open(src) as pdf:
        pdf.save(dest, encryption=pikepdf.Encryption(user=user, owner="owner", allow=allow))


def is_unencrypted(path: Path) -> bool:
    with pikepdf.open(path) as pdf:
        return not pdf.is_encrypted


def main() -> int:
    pdf_unlocker = load_module()
    run_root = ROOT / "work" / f"test_run_{int(time.time())}"
    input_dir = run_root / "input"
    nested_dir = input_dir / "nested"
    output_dir = run_root / "output"
    nested_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    base = run_root / "base.pdf"
    plain = input_dir / "plain.pdf"
    upper = input_dir / "UPPER.PDF"
    user_locked = run_root / "user_locked.pdf"
    owner_locked = nested_dir / "owner_locked.pdf"
    not_pdf = run_root / "not_pdf.pdf"

    make_blank_pdf(base)
    make_blank_pdf(plain)
    make_blank_pdf(upper)
    make_encrypted_pdf(base, user_locked, user="secret")
    make_encrypted_pdf(base, owner_locked, restrict=True)
    not_pdf.write_text("not a real pdf", encoding="utf-8")

    checks: list[tuple[str, bool]] = []

    status, _ = pdf_unlocker.unlock_pdf(user_locked, run_root / "user_unlocked.pdf", "secret")
    checks.append(("correct password", status == "ok" and is_unencrypted(run_root / "user_unlocked.pdf")))

    status, _ = pdf_unlocker.unlock_pdf(user_locked, run_root / "wrong_password.pdf", "wrong")
    checks.append(("wrong password", status == "wrong_password"))

    status, _ = pdf_unlocker.unlock_pdf(owner_locked, run_root / "owner_unlocked.pdf", "")
    checks.append(("owner password empty", status == "ok" and is_unencrypted(run_root / "owner_unlocked.pdf")))

    status, _ = pdf_unlocker.unlock_pdf(not_pdf, run_root / "not_pdf_out.pdf", "")
    checks.append(("non pdf error", status == "error"))

    folder_stats = pdf_unlocker.unlock_folder(input_dir, output_dir, "", log=lambda _msg: None)
    checks.append(("folder batch", folder_stats == {"total": 3, "ok": 3, "wrong_password": 0, "error": 0}))

    file_output = run_root / "file_output"
    file_stats = pdf_unlocker.unlock_pdf_files([plain, user_locked], file_output, "secret", log=lambda _msg: None)
    checks.append(("file batch", file_stats == {"total": 2, "ok": 2, "wrong_password": 0, "error": 0}))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print("FAILED")
        for name in failed:
            print(f"- {name}")
        return 1

    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
