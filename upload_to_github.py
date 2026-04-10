#!/usr/bin/env python3
"""
Script to automatically upload training_data.json to GitHub.
This can be run standalone or called from the preprocessing script.

Usage:
    python upload_to_github.py
    
Or set AUTO_UPLOAD=True in preprocess_training_data.py
"""

import subprocess
import os
import sys
import shutil
import tempfile

# Configuration
REPO_PATH = "."  # Current directory (or path to your git repo)
GITHUB_REPO = "YOUR_GITHUB_HANDLE/YOUR_SHOWCASE_REPO"  # Your GitHub username/repo
BRANCH = "main"
FILE_TO_UPLOAD = "training_data.json"
COMMIT_MESSAGE = "Update training data (auto-generated)"

def check_git_installed():
    """Check if Git is installed."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def check_git_repo():
    """Check if current directory is a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=REPO_PATH,
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False

def init_git_repo():
    """Initialize git repository if it doesn't exist."""
    print("Initializing Git repository...")
    try:
        subprocess.run(
            ["git", "init"],
            cwd=REPO_PATH,
            check=True
        )
        print("✓ Git repository initialized")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to initialize Git repository: {e}")
        return False

def check_file_exists():
    """Check if training_data.json exists."""
    file_path = os.path.join(REPO_PATH, FILE_TO_UPLOAD)
    return os.path.exists(file_path)

def upload_with_git():
    """Upload file to GitHub using Git commands."""
    print(f"\n{'='*60}")
    print("Uploading to GitHub...")
    print(f"{'='*60}\n")
    
    try:
        # Check if file exists
        if not check_file_exists():
            print(f"✗ Error: {FILE_TO_UPLOAD} not found!")
            print("   Run preprocess_training_data.py first to generate it.")
            return False
        
        # Add file to git
        print("1. Staging file...")
        subprocess.run(
            ["git", "add", FILE_TO_UPLOAD],
            cwd=REPO_PATH,
            check=True
        )
        print("   ✓ File staged")
        
        # Check if there are changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=REPO_PATH,
            capture_output=True
        )
        if result.returncode == 0:
            print("   ℹ No changes to commit (file is up to date)")
            return True
        
        # Commit
        print("2. Committing changes...")
        # Check if this is the first commit (no commits yet)
        try:
            subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"],
                cwd=REPO_PATH,
                capture_output=True,
                check=True
            )
            # Not first commit, proceed normally
            subprocess.run(
                ["git", "commit", "-m", COMMIT_MESSAGE],
                cwd=REPO_PATH,
                check=True
            )
        except subprocess.CalledProcessError:
            # First commit - might need to set branch name
            subprocess.run(
                ["git", "commit", "-m", COMMIT_MESSAGE],
                cwd=REPO_PATH,
                check=True
            )
            # Set branch name if not set
            try:
                subprocess.run(
                    ["git", "branch", "-M", BRANCH],
                    cwd=REPO_PATH,
                    check=True
                )
            except:
                pass
        
        print("   ✓ Changes committed")
        
        # Check if we're in a rebase/merge state and abort if needed
        try:
            rebase_check = subprocess.run(
                ["git", "rev-parse", "--git-path", "rebase-merge"],
                cwd=REPO_PATH,
                capture_output=True
            )
            if rebase_check.returncode == 0:
                print("   ⚠ Aborting previous rebase...")
                subprocess.run(["git", "rebase", "--abort"], cwd=REPO_PATH, capture_output=True)
        except:
            pass
        
        # Make sure we're on the main branch (not detached HEAD)
        try:
            current_branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=REPO_PATH,
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()
            
            if current_branch != BRANCH and current_branch == "HEAD":
                print(f"   ⚠ Detached HEAD detected, checking out {BRANCH}...")
                subprocess.run(
                    ["git", "checkout", BRANCH],
                    cwd=REPO_PATH,
                    check=True
                )
        except:
            pass
        
        # Pull latest changes before pushing (to avoid conflicts)
        print("3. Syncing with GitHub...")
        try:
            # Fetch latest from remote
            subprocess.run(
                ["git", "fetch", "origin", BRANCH],
                cwd=REPO_PATH,
                capture_output=True,
                check=True
            )
            
            # Try to pull with allow-unrelated-histories if needed
            try:
                result = subprocess.run(
                    ["git", "pull", "origin", BRANCH, "--no-rebase", "--allow-unrelated-histories"],
                    cwd=REPO_PATH,
                    capture_output=True,
                    text=True,
                    check=True
                )
                print("   ✓ Synced with remote")
            except subprocess.CalledProcessError:
                # If pull fails due to unrelated histories or conflicts, reset to remote
                print("   ⚠ Unrelated histories detected, resetting to remote...")
                try:
                    # Save our training_data.json temporarily
                    temp_file = os.path.join(tempfile.gettempdir(), "training_data_backup.json")
                    if os.path.exists(FILE_TO_UPLOAD):
                        shutil.copy2(FILE_TO_UPLOAD, temp_file)
                    
                    # Reset to match remote
                    subprocess.run(
                        ["git", "reset", "--hard", f"origin/{BRANCH}"],
                        cwd=REPO_PATH,
                        check=True
                    )
                    
                    # Restore our file
                    if os.path.exists(temp_file):
                        shutil.copy2(temp_file, FILE_TO_UPLOAD)
                        os.remove(temp_file)
                        # Re-stage it
                        subprocess.run(["git", "add", FILE_TO_UPLOAD], cwd=REPO_PATH, check=True)
                        # Check if there are changes to commit
                        result = subprocess.run(
                            ["git", "diff", "--cached", "--quiet"],
                            cwd=REPO_PATH,
                            capture_output=True
                        )
                        if result.returncode != 0:
                            # There are changes, commit them
                            subprocess.run(
                                ["git", "commit", "-m", COMMIT_MESSAGE],
                                cwd=REPO_PATH,
                                check=True
                            )
                            print("   ✓ Reset to remote and restored training_data.json (committed)")
                        else:
                            print("   ✓ Reset to remote (file unchanged)")
                    
                except Exception as reset_error:
                    print(f"   ⚠ Reset failed: {reset_error}")
                    print("   Continuing with push anyway...")
        except subprocess.CalledProcessError as fetch_error:
            error_msg = fetch_error.stderr.lower() if fetch_error.stderr else ""
            if "couldn't find remote ref" in error_msg:
                print("   ℹ No remote branch found (first push)")
            else:
                print(f"   ⚠ Sync had issues: {fetch_error.stderr}")
                print("   Continuing with push anyway...")
        
        # Push to GitHub
        print("4. Pushing to GitHub...")
        # Use -u flag for first push to set upstream
        try:
            subprocess.run(
                ["git", "push", "-u", "origin", BRANCH],
                cwd=REPO_PATH,
                check=True
            )
        except subprocess.CalledProcessError:
            # If -u fails, try without it (might already be set)
            subprocess.run(
                ["git", "push", "origin", BRANCH],
                cwd=REPO_PATH,
                check=True
            )
        print("   ✓ Pushed to GitHub")
        
        print(f"\n{'='*60}")
        print("✓ Successfully uploaded to GitHub!")
        print(f"  File: {FILE_TO_UPLOAD}")
        print(f"  Repository: {GITHUB_REPO}")
        print(f"  Branch: {BRANCH}")
        print(f"{'='*60}\n")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error during Git operation: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you're in a Git repository")
        print("2. Make sure you have a remote 'origin' configured")
        print("3. Make sure you're authenticated with GitHub")
        print("4. Try running manually:")
        print(f"   git add {FILE_TO_UPLOAD}")
        print(f"   git commit -m \"{COMMIT_MESSAGE}\"")
        print(f"   git push origin {BRANCH}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return False

def upload_with_github_cli():
    """Upload file to GitHub using GitHub CLI (gh)."""
    print(f"\n{'='*60}")
    print("Uploading to GitHub using GitHub CLI...")
    print(f"{'='*60}\n")
    
    try:
        # Check if gh is installed
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
        
        # Read file content
        with open(FILE_TO_UPLOAD, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Upload using gh
        result = subprocess.run(
            ["gh", "repo", "edit", GITHUB_REPO, "--file", f"{FILE_TO_UPLOAD}:{content}"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✓ Successfully uploaded to GitHub!")
            return True
        else:
            print(f"✗ Error: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("✗ GitHub CLI (gh) not found. Install it from: https://cli.github.com/")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Main function."""
    # Check prerequisites
    if not check_git_installed():
        print("✗ Git is not installed. Please install Git first.")
        print("  Download from: https://git-scm.com/downloads")
        sys.exit(1)
    
    if not check_git_repo():
        print("⚠ Current directory is not a Git repository.")
        print("\nSetting up Git repository...")
        
        # Initialize git repo
        if not init_git_repo():
            sys.exit(1)
        
        # Add remote (user will need to configure authentication)
        print("\nAdding GitHub remote...")
        try:
            subprocess.run(
                ["git", "remote", "add", "origin", f"https://github.com/{GITHUB_REPO}.git"],
                cwd=REPO_PATH,
                check=True
            )
            print("✓ Remote added")
            print("\n⚠ IMPORTANT: Configure authentication before pushing:")
            print(f"   git remote set-url origin https://YOUR_TOKEN@github.com/{GITHUB_REPO}.git")
            print("\nOr if you already have a token configured, continuing...")
        except subprocess.CalledProcessError:
            # Remote might already exist, try to set URL
            try:
                subprocess.run(
                    ["git", "remote", "set-url", "origin", f"https://github.com/{GITHUB_REPO}.git"],
                    cwd=REPO_PATH,
                    check=True
                )
                print("✓ Remote URL updated")
            except:
                pass
    
    if not check_file_exists():
        print(f"✗ {FILE_TO_UPLOAD} not found!")
        print("   Run preprocess_training_data.py first to generate it.")
        sys.exit(1)
    
    # Try uploading with Git
    success = upload_with_git()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()

