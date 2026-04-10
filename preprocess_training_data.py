#!/usr/bin/env python3
"""
Pre-processing script to fetch training data from links and save to a JSON file.
Run this script whenever you update training_links.txt to regenerate the pre-processed data.

Usage: python preprocess_training_data.py
"""

import json
import requests
from bs4 import BeautifulSoup
import time
import sys
import os
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager

# Configuration
LINKS_URL = "https://raw.githubusercontent.com/YOUR_GITHUB_HANDLE/YOUR_SHOWCASE_REPO/refs/heads/main/training_links.txt"
OUTPUT_FILE = "training_data.json"
# Auto-upload is disabled in GitHub Actions (handled by workflow)
AUTO_UPLOAD = os.environ.get("GITHUB_ACTIONS") != "true"  # True unless running in GitHub Actions

def fetch_with_retry(url, max_retries=3, timeout=10):
    """Fetch URL with retry logic and CORS proxy fallback."""
    proxies = [
        f"https://api.allorigins.win/raw?url={url}",
        f"https://corsproxy.io/?{url}",
        url  # Try direct last
    ]
    
    for attempt in range(max_retries):
        for proxy_url in proxies:
            try:
                response = requests.get(proxy_url, timeout=timeout)
                if response.status_code == 200:
                    return response.text
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"  Failed after {max_retries} attempts: {e}")
                continue
        time.sleep(0.5)  # Small delay between retries
    
    return None

def setup_selenium_driver():
    """Setup and return a Selenium WebDriver with Chrome in headless mode."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print(f"  ⚠ Warning: Could not setup Selenium: {e}")
        print(f"  Falling back to basic HTML scraping...")
        return None

def expand_all_content(driver, wait_time=3):
    """Find and click all expandable elements to reveal hidden content."""
    try:
        # Wait for page to load
        time.sleep(2)
        
        # FIRST: Force-show all hidden content using JavaScript
        # This handles content that's in the DOM but hidden by CSS (the "gray" code in inspector)
        try:
            force_show_script = """
            (function() {
                // 1. Remove Bootstrap collapse classes and show collapsed content
                var collapsedElements = document.querySelectorAll('.collapse:not(.show), .collapsing');
                collapsedElements.forEach(function(el) {
                    el.classList.remove('collapse', 'collapsing');
                    el.classList.add('show');
                    el.style.display = 'block';
                    el.style.visibility = 'visible';
                    el.style.height = 'auto';
                    el.setAttribute('aria-expanded', 'true');
                });
                
                // 2. Show all elements with display: none or visibility: hidden
                var allElements = document.querySelectorAll('*');
                allElements.forEach(function(el) {
                    var style = window.getComputedStyle(el);
                    if (style.display === 'none' && el.offsetParent === null) {
                        // Check if it's not a script, style, or hidden by design
                        var tag = el.tagName.toLowerCase();
                        if (tag !== 'script' && tag !== 'style' && tag !== 'noscript' && 
                            !el.classList.contains('d-none') && 
                            !el.hasAttribute('hidden')) {
                            el.style.display = '';
                            el.style.visibility = 'visible';
                        }
                    }
                    if (style.visibility === 'hidden' && el.offsetParent === null) {
                        var tag = el.tagName.toLowerCase();
                        if (tag !== 'script' && tag !== 'style' && tag !== 'noscript') {
                            el.style.visibility = 'visible';
                        }
                    }
                });
                
                // 3. Expand all accordion/collapse panels
                var collapsePanels = document.querySelectorAll('[class*="collapse"]:not(.show)');
                collapsePanels.forEach(function(el) {
                    el.classList.add('show');
                    el.classList.remove('collapse', 'collapsing');
                    el.style.display = 'block';
                    el.setAttribute('aria-expanded', 'true');
                });
                
                // 4. Remove aria-hidden attributes
                var hiddenElements = document.querySelectorAll('[aria-hidden="true"]');
                hiddenElements.forEach(function(el) {
                    // Only if it's not a decorative element
                    if (!el.classList.contains('sr-only') && 
                        !el.classList.contains('visually-hidden')) {
                        el.setAttribute('aria-hidden', 'false');
                        var style = window.getComputedStyle(el);
                        if (style.display === 'none') {
                            el.style.display = '';
                        }
                    }
                });
                
                // 5. Force expand Bootstrap accordions
                var accordionButtons = document.querySelectorAll('[data-bs-toggle="collapse"], [data-toggle="collapse"]');
                accordionButtons.forEach(function(btn) {
                    var targetId = btn.getAttribute('data-bs-target') || btn.getAttribute('data-target') || btn.getAttribute('href');
                    if (targetId) {
                        if (targetId.startsWith('#')) targetId = targetId.substring(1);
                        var target = document.getElementById(targetId) || document.querySelector(targetId);
                        if (target) {
                            target.classList.add('show');
                            target.classList.remove('collapse', 'collapsing');
                            target.style.display = 'block';
                            target.setAttribute('aria-expanded', 'true');
                            btn.setAttribute('aria-expanded', 'true');
                            btn.classList.remove('collapsed');
                        }
                    }
                });
                
                // 6. AGGRESSIVE: Show ALL hidden elements (catch everything, including Odoo)
                // This is more aggressive - shows anything that's hidden unless it's clearly not content
                var allElements = document.querySelectorAll('*');
                allElements.forEach(function(el) {
                    var tag = el.tagName.toLowerCase();
                    // Skip script, style, noscript, and meta tags
                    if (tag === 'script' || tag === 'style' || tag === 'noscript' || tag === 'meta' || tag === 'link') {
                        return;
                    }
                    
                    var style = window.getComputedStyle(el);
                    var isHidden = style.display === 'none' || 
                                   style.visibility === 'hidden' || 
                                   style.opacity === '0' ||
                                   el.offsetParent === null ||
                                   el.hasAttribute('hidden') ||
                                   el.classList.contains('d-none') ||
                                   el.classList.contains('hidden') ||
                                   el.classList.contains('o_hidden');
                    
                    // If hidden and not a structural/system element, show it
                    if (isHidden) {
                        // Check if it has text content or child elements with content
                        var hasContent = el.textContent.trim().length > 0 || 
                                       el.querySelector('img, video, iframe') !== null ||
                                       el.children.length > 0;
                        
                        // Show if it has content or is an Odoo element
                        if (hasContent || el.classList.toString().includes('o_') || el.hasAttribute('contenteditable')) {
                            el.style.display = '';
                            el.style.visibility = 'visible';
                            el.style.opacity = '1';
                            el.style.height = 'auto';
                            el.style.maxHeight = 'none';
                            el.classList.remove('d-none', 'hidden', 'collapse', 'o_hidden', 'collapsed');
                            el.removeAttribute('hidden');
                            el.setAttribute('aria-expanded', 'true');
                        }
                    }
                });
                
                // 7. Special Odoo handling - force show all Odoo classes
                var odooSelectors = [
                    '[class*="o_"]',
                    '[contenteditable="true"]',
                    '.o_editable',
                    '.note-editable',
                    '[class*="o_field"]',
                    '[class*="o_website"]',
                    '[class*="o_snippet"]',
                    '[class*="o_field_widget"]',
                    '[class*="o_website_block"]',
                    '.tab-pane', // Bootstrap tabs
                    '[role="tabpanel"]' // ARIA tabs
                ];
                
                odooSelectors.forEach(function(selector) {
                    try {
                        var elements = document.querySelectorAll(selector);
                        elements.forEach(function(el) {
                            el.style.display = '';
                            el.style.visibility = 'visible';
                            el.style.opacity = '1';
                            el.style.height = 'auto';
                            el.style.maxHeight = 'none';
                            el.classList.remove('d-none', 'hidden', 'collapse', 'o_hidden', 'collapsed', 'fade');
                            el.classList.add('active', 'show'); // For tabs
                            el.removeAttribute('hidden');
                        });
                    } catch(e) {}
                });
                
                // 8. Click all Odoo expand/collapse buttons if they exist
                var odooButtons = document.querySelectorAll('[class*="o_btn"], [class*="o_toggle"], button[class*="o_"], a[class*="o_"]');
                odooButtons.forEach(function(btn) {
                    var text = (btn.textContent || '').toLowerCase();
                    if (text.includes('expand') || text.includes('show') || text.includes('more') || 
                        btn.getAttribute('aria-expanded') === 'false') {
                        try {
                            btn.click();
                        } catch(e) {}
                    }
                });

                // 9. Activate all tabs
                var tabs = document.querySelectorAll('[data-toggle="tab"], [data-bs-toggle="tab"], [role="tab"], .nav-link');
                tabs.forEach(function(tab) {
                    try {
                        tab.classList.add('active');
                        var targetId = tab.getAttribute('href') || tab.getAttribute('data-target') || tab.getAttribute('data-bs-target');
                        if (targetId && targetId.startsWith('#')) {
                            var target = document.querySelector(targetId);
                            if (target) {
                                target.classList.add('active', 'show');
                                target.style.display = 'block';
                            }
                        }
                    } catch(e) {}
                });
                
                return 'Forced show complete';
            })();
            """
            result = driver.execute_script(force_show_script)
            time.sleep(1.5)  # Wait longer for Odoo content to render
            print(f"  ✓ Force-showed hidden CSS content (including Odoo)")
            
            # Additional wait and scroll to trigger Odoo lazy loading
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
            
            # Run force-show one more time after scrolling (Odoo might load content on scroll)
            try:
                driver.execute_script(force_show_script)
                time.sleep(0.5)
            except:
                pass
        except Exception as e:
            print(f"  ⚠ Could not force-show CSS content: {e}")
        
        # Scroll to load lazy content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        
        # Track clicked elements to prevent duplicates (this fixes the 97 clicks issue)
        clicked_elements = set()
        expanded_count = 0
        max_iterations = 4  # Reduced - most should be handled by force-show script
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            found_any = False
            
            # More specific selectors - only target truly expandable elements (not already expanded)
            selectors = [
                # Only unexpanded elements
                "button[aria-expanded='false']",
                "a[aria-expanded='false']",
                "[data-bs-toggle='collapse'][aria-expanded='false']",
                "[data-toggle='collapse'][aria-expanded='false']",
                
                # Tabs
                "[role='tab']",
                ".nav-link",
                
                # Text-based (only if not already expanded)
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show more') and not(@aria-expanded='true')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'read more') and not(@aria-expanded='true')]",
                "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show more') and not(@aria-expanded='true')]",
                
                # Generic "Show" buttons often used in Odoo
                "//button[contains(text(), 'Show')]",
                "//a[contains(text(), 'Show')]",
            ]
            
            for selector in selectors:
                try:
                    if selector.startswith("//"):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        try:
                            # Create unique ID for element to prevent duplicate clicks
                            try:
                                element_id = element.get_attribute('id') or ''
                                element_class = element.get_attribute('class') or ''
                                element_text = (element.text or '')[:30]
                                unique_id = f"{element.tag_name}_{element_id}_{element_class}_{element_text}"
                            except:
                                try:
                                    location = element.location
                                    unique_id = f"{element.tag_name}_{location['x']}_{location['y']}"
                                except:
                                    continue
                            
                            # Skip if already clicked
                            if unique_id in clicked_elements:
                                continue
                            
                            # Check if element is visible and clickable
                            if element.is_displayed():
                                # Double-check it's actually collapsed (unless it's a tab)
                                aria_expanded = element.get_attribute('aria-expanded')
                                role = element.get_attribute('role')
                                is_tab = role == 'tab' or 'nav-link' in (element.get_attribute('class') or '')
                                
                                if aria_expanded == 'true' and not is_tab:
                                    continue  # Already expanded, skip
                                
                                # Scroll element into view
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                                time.sleep(0.2)
                                
                                # Try clicking
                                try:
                                    element.click()
                                    clicked_elements.add(unique_id)
                                    found_any = True
                                    expanded_count += 1
                                    time.sleep(0.4)  # Reduced wait time
                                except (ElementClickInterceptedException, NoSuchElementException):
                                    # Try JavaScript click as fallback
                                    try:
                                        driver.execute_script("arguments[0].click();", element)
                                        clicked_elements.add(unique_id)
                                        found_any = True
                                        expanded_count += 1
                                        time.sleep(0.4)
                                    except:
                                        pass
                        except Exception:
                            continue
                except:
                    continue
            
            # If no more expandable elements found, break
            if not found_any:
                break
            
            # Scroll down to find more elements
            driver.execute_script("window.scrollBy(0, 400);")
            time.sleep(0.3)
        
        if expanded_count > 0:
            print(f"  ✓ Expanded {expanded_count} hidden sections")
        
        # Final pass: Force-show any remaining hidden content (including Odoo)
        final_show_script = """
        (function() {
            // Final pass to catch anything we missed
            var allHidden = document.querySelectorAll('.collapse:not(.show), [style*="display: none"], [style*="display:none"]');
            allHidden.forEach(function(el) {
                var tag = el.tagName.toLowerCase();
                if (tag !== 'script' && tag !== 'style' && tag !== 'noscript') {
                    el.classList.remove('collapse', 'collapsing', 'd-none');
                    el.classList.add('show');
                    el.style.display = '';
                    el.style.visibility = 'visible';
                    el.style.height = 'auto';
                    el.setAttribute('aria-expanded', 'true');
                    el.removeAttribute('hidden');
                }
            });
            
            // Final aggressive pass - show ALL hidden content including Odoo
            var allHidden = document.querySelectorAll('*');
            allHidden.forEach(function(el) {
                var tag = el.tagName.toLowerCase();
                if (tag === 'script' || tag === 'style' || tag === 'noscript' || tag === 'meta' || tag === 'link') {
                    return;
                }
                
                var style = window.getComputedStyle(el);
                var isHidden = style.display === 'none' || 
                               style.visibility === 'hidden' || 
                               style.opacity === '0' ||
                               el.offsetParent === null;
                
                // If hidden and has content or is Odoo-related, show it
                if (isHidden) {
                    var hasContent = el.textContent.trim().length > 0 || 
                                   el.querySelector('img, video, iframe') !== null ||
                                   el.children.length > 0 ||
                                   el.classList.toString().includes('o_') ||
                                   el.hasAttribute('contenteditable');
                    
                    if (hasContent) {
                        el.style.display = '';
                        el.style.visibility = 'visible';
                        el.style.opacity = '1';
                        el.style.height = 'auto';
                        el.style.maxHeight = 'none';
                        el.classList.remove('d-none', 'hidden', 'collapse', 'o_hidden', 'collapsed');
                        el.removeAttribute('hidden');
                    }
                }
            });
            
            return 'Final show complete';
        })();
        """
        try:
            driver.execute_script(final_show_script)
            time.sleep(0.5)
        except:
            pass
        
        # Final scroll to bottom to load any lazy-loaded content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_time)
        
        # One more scroll up and down to trigger any remaining lazy loads
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        
        # One last force-show pass after all scrolling
        try:
            driver.execute_script(final_show_script)
            time.sleep(0.5)
        except:
            pass
        
    except Exception as e:
        print(f"  ⚠ Warning during expansion: {e}")

def extract_text_from_html(html):
    """Extract clean text from HTML."""
    if not html:
        return ""
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style", "noscript"]):
            script.decompose()
        
        # Get text and clean it up
        text = soup.get_text()
        # Replace multiple whitespace with single space
        text = ' '.join(text.split())
        return text.strip()
    except Exception as e:
        print(f"  Error parsing HTML: {e}")
        # Fallback: simple regex-based extraction
        import re
        text = re.sub(r'<[^>]+>', ' ', html)
        text = ' '.join(text.split())
        return text.strip()

def scrape_with_selenium(url, driver, timeout=30):
    """Scrape a URL using Selenium to get all content including JavaScript-rendered and hidden content."""
    try:
        # Check if driver session is still valid
        try:
            driver.current_url
        except:
            raise Exception("Driver session invalid")
        
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        
        # Wait for page to be interactive
        WebDriverWait(driver, min(timeout, 20)).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Additional wait for JavaScript to finish executing
        time.sleep(1)
        
        # Expand all hidden content
        expand_all_content(driver, wait_time=2.5)
        
        # Get the final HTML after all expansions
        html = driver.page_source
        
        # Extract text
        text = extract_text_from_html(html)
        return text
        
    except TimeoutException:
        print(f"  ⚠ Page load timeout")
        return None
    except Exception as e:
        error_msg = str(e)
        if "invalid session id" in error_msg.lower() or "session" in error_msg.lower():
            raise Exception("Driver session invalid")  # Re-raise to trigger driver recreation
        print(f"  ⚠ Error with Selenium: {e}")
        return None

def load_training_data():
    """Load training data from all links."""
    print("Reading links list locally...")
    try:
        with open("training_links.txt", "r", encoding="utf-8") as f:
            links_text = f.read()
        
        links = [line.strip() for line in links_text.split('\n') if line.strip()]
        print(f"Found {len(links)} links to process\n")
        
        # Setup Selenium driver (will be None if Selenium is not available)
        driver = setup_selenium_driver()
        use_selenium = driver is not None
        
        if use_selenium:
            print("Using Selenium for full content extraction (including hidden elements)...\n")
        else:
            print("Using basic HTML scraping (Selenium not available)...\n")
        
        training_data = {}
        valid_links = []
        
        # Proactively restart driver every N pages to prevent crashes
        DRIVER_RESTART_INTERVAL = 5  # Restart every 5 pages
        
        for i, link in enumerate(links, 1):
            print(f"[{i}/{len(links)}] Processing: {link}")
            valid_links.append(link)
            
            # Proactively restart driver every N pages to prevent crashes
            if use_selenium and i > 1 and (i - 1) % DRIVER_RESTART_INTERVAL == 0:
                print(f"  🔄 Proactively restarting driver (every {DRIVER_RESTART_INTERVAL} pages)...")
                try:
                    driver.quit()
                except:
                    pass
                driver = setup_selenium_driver()
                if not driver:
                    print(f"  ⚠ Could not recreate driver, falling back to basic scraping")
                    use_selenium = False
            
            text = None
            
            # Try Selenium first if available
            if use_selenium:
                try:
                    text = scrape_with_selenium(link, driver, timeout=30)
                except Exception as e:
                    error_msg = str(e).lower()
                    # If session is invalid, try to recreate driver
                    if "session" in error_msg or "invalid" in error_msg:
                        print(f"  ⚠ Driver session lost, recreating...")
                        try:
                            driver.quit()
                        except:
                            pass
                        driver = setup_selenium_driver()
                        if driver:
                            # Retry once with new driver
                            try:
                                text = scrape_with_selenium(link, driver, timeout=30)
                            except:
                                text = None
                        else:
                            print(f"  ⚠ Could not recreate driver, falling back to basic scraping")
                            use_selenium = False
                            text = None
                    else:
                        print(f"  ⚠ Selenium failed: {e}")
                        text = None
            
            # Fallback to basic HTML scraping if Selenium failed or not available
            if not text:
                html = fetch_with_retry(link)
                if html:
                    text = extract_text_from_html(html)
            
            if text:
                # Store all text (no character limit - we want ALL content)
                training_data[link] = text
                print(f"  ✓ Loaded {len(text)} characters")
            else:
                print(f"  ✗ Failed to load")
                training_data[link] = ""  # Store empty string for failed links
        
        # Close Selenium driver if it was opened
        if driver:
            try:
                driver.quit()
            except:
                pass
        
        return {
            "valid_links": valid_links,
            "training_data": training_data,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    except Exception as e:
        print(f"Error: {e}")
        # Make sure to close driver on error
        try:
            if 'driver' in locals() and driver:
                driver.quit()
        except:
            pass
        return None

def main():
    print("=" * 60)
    print("Training Data Pre-processor")
    print("=" * 60)
    print()
    
    data = load_training_data()
    
    if data:
        print(f"\nSaving to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        loaded_count = sum(1 for v in data["training_data"].values() if v)
        print(f"✓ Successfully processed {loaded_count}/{len(data['valid_links'])} links")
        print(f"✓ Data saved to {OUTPUT_FILE}")
        
        # Auto-upload to GitHub if enabled
        if AUTO_UPLOAD:
            print(f"\n{'='*60}")
            print("Auto-uploading to GitHub...")
            print(f"{'='*60}")
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, "upload_to_github.py"],
                    capture_output=False
                )
                if result.returncode == 0:
                    print("\n✓ All done! The chatbot will now load instantly!")
                else:
                    print("\n⚠ Upload failed. You can manually run: python upload_to_github.py")
            except Exception as e:
                print(f"\n⚠ Auto-upload failed: {e}")
                print("   You can manually run: python upload_to_github.py")
        else:
            print(f"\nNext steps:")
            print(f"1. Upload {OUTPUT_FILE} to your GitHub repository")
            print(f"2. Or run: python upload_to_github.py")
            print(f"3. The chatbot will now load instantly!")
    else:
        print("\n✗ Failed to process training data")

if __name__ == "__main__":
    main()

