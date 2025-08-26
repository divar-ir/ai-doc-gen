# run_doc_generator.py
import argparse
import asyncio
import os
import sys
from pathlib import Path

# افزودن مسیر ai-doc-gen به مسیرهای پایتون
sys.path.append(os.path.join(os.path.dirname(__file__), 'ai-doc-gen'))

# وارد کردن کلاس‌های مورد نیاز از مسیر صحیح
from src.handlers.readme import ReadmeHandler, ReadmeHandlerConfig

async def main():
    """
    این اسکریپت با استفاده از ReadmeHandler، مستندات (فایل README.md)
    را برای کل پروژه بازسازی می‌کند.
    """
    parser = argparse.ArgumentParser(description="Generate project README documentation.")
    parser.add_argument(
        "--project-root",
        required=True,
        help="The root directory of the project to document."
    )
    args = parser.parse_args()

    print(f"Starting documentation generation for project at: {args.project_root}")

    try:
        # مرحله ۱: ساختن شیء کانفیگ
        # بر اساس تحلیل کد، فقط به repo_path نیاز داریم. بقیه پارامترها
        # یا اختیاری هستند یا از فایل کانفیگ اصلی خوانده می‌شوند.
        config = ReadmeHandlerConfig(
            repo_path=Path(args.project_root)
        )

        # مرحله ۲: ساختن یک نمونه از ReadmeHandler
        handler = ReadmeHandler(config)

        # مرحله ۳: فراخوانی متد handle برای شروع فرآیند
        # این متد به صورت خودکار فایل README.md را در ریشه پروژه ایجاد یا بازنویسی می‌کند
        await handler.handle()
        
        print(f"Documentation successfully generated at: {Path(args.project_root) / 'README.md'}")

    except Exception as e:
        print(f"An error occurred during documentation generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
