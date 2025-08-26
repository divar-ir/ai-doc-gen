import argparse
import asyncio
import os
import sys
from pathlib import Path

# مسیر پوشه ai-doc-gen را به مسیرهای پایتون اضافه می‌کنیم
# تا بتوانیم ماژول‌های آن را وارد کنیم
sys.path.append(os.path.join(os.path.dirname(__file__), 'ai-doc-gen'))

# --- بخش کلیدی ---
# کلاس‌های مورد نیاز را از ماژول صحیح وارد می‌کنیم
from handlers.readme import ReadmeHandler, ReadmeHandlerConfig
from config import load_config  # ممکن است به این هم نیاز داشته باشیم

async def main():
    """
    این اسکریپت یک فایل کد را به عنوان ورودی می‌گیرد و با استفاده از ReadmeHandler
    برای آن مستندات تولید می‌کند.
    """
    parser = argparse.ArgumentParser(description="Generate documentation for a single file using ReadmeHandler.")
    # ما همچنان مسیر فایل را می‌گیریم تا بدانیم کدام فایل تغییر کرده است
    parser.add_argument("--file-path", required=True, help="Path to the source code file that changed.")
    # مسیر ریشه پروژه اصلی شما (ERP)
    parser.add_argument("--project-root", required=True, help="The root directory of the main project.")
    # مسیر خروجی برای مستندات
    parser.add_argument("--output-path", required=True, help="Path to save the generated README.md file.")
    
    args = parser.parse_args()

    print(f"Triggering documentation generation due to changes in: {args.file_path}")

    try:
        # مرحله ۱: ساختن شیء کانفیگ (ReadmeHandlerConfig)
        # شما باید فایل handlers/readme.py را باز کنید و ببینید کلاس ReadmeHandlerConfig
        # دقیقاً چه پارامترهایی را می‌پذیرد. در اینجا ما مهم‌ترین‌ها را حدس می‌زنیم.
        config = ReadmeHandlerConfig(
            repo_path=Path(args.project_root),
            output_path=Path(args.output_path),
            # ممکن است پارامترهای دیگری هم نیاز باشد که باید به صورت دستی اضافه کنید
            # مثلا: llm_config, prompt_config و ...
            # برای پیدا کردن آن‌ها، تعریف کلاس ReadmeHandlerConfig را ببینید.
        )

        # مرحله ۲: ساختن یک نمونه از ReadmeHandler
        handler = ReadmeHandler(config)

        # مرحله ۳: فراخوانی متد handle برای شروع فرآیند
        # این متد احتمالاً خودش فایل را در output_path ذخیره می‌کند.
        await handler.handle()
        
        print(f"Documentation successfully generated/updated at: {args.output_path}")

    except Exception as e:
        print(f"An error occurred during documentation generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
