import argparse
from multiprocessing import Process, freeze_support
# Explicit import forces PyInstaller to bundle the Edge driver
import selenium.webdriver.edge.webdriver

from bot import BingRewardsBot

PROFILES = [
    r"D:\profiles\profile1",
    r"D:\profiles\profile2",
]

def worker(profile_path: str, searches: int, headless: bool):
    bot = BingRewardsBot(profile_path=profile_path, headless=headless)
    bot.execute_searches(count=searches)

def main():
    parser = argparse.ArgumentParser(description="Parallel Multi-Account Launcher")
    parser.add_argument("-c", "-s", "--count", "--searches", type=int, default=30,
                        help="Number of searches per account (default: 30)")
    parser.add_argument("--headless", action="store_true", help="Run browsers in headless mode")
    args = parser.parse_args()

    searches = args.count

    processes = []
    print(f"[*] Launching {len(PROFILES)} parallel instances ({searches} searches per account)...\n")

    for path in PROFILES:
        p = Process(target=worker, args=(path, searches, args.headless))
        p.start()
        processes.append(p)

    try:
        for p in processes:
            p.join()
        print("\n[+] All tasks finished.")
    except KeyboardInterrupt:
        print("\n[!] Terminating active processes...")
        for p in processes:
            p.terminate()

if __name__ == "__main__":
    freeze_support()  # Prevents argparse errors in PyInstaller child processes
    main()
