import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import csv
import time
import pandas as pd
import platform
import sys

# Set page config
st.set_page_config(page_title="Auction Scraper", layout="wide")

# Streamlit interface
st.title("Auction Scraper with Pagination")

# Add instructions for users
with st.expander("📋 Instructions", expanded=True):
    st.markdown("""
    1. Select the auction date from the calendar below
    2. Click 'Run Scraper' to start the process
    3. The tool will automatically handle ChromeDriver installation
    4. Results will be displayed below and saved to 'auction_details.csv'
    
    Note: First-time setup might take a few moments as necessary components are installed.
    """)

# User input for the auction date
auction_date = st.date_input("Select Auction Date")
run_button = st.button("Run Scraper")

def wait_for_element_text(driver, by, value, timeout=20, retries=3):
    """Wait for an element to have non-empty text content"""
    for attempt in range(retries):
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            text = element.text.strip()
            if text:
                return text
            time.sleep(2)  # Wait between retries
        except (TimeoutException, StaleElementReferenceException):
            if attempt == retries - 1:
                raise
            time.sleep(2)
    return None

def setup_webdriver():
    """Setup and return configured Chrome WebDriver"""
    try:
        # Chrome options for better compatibility
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        # Add Windows-specific options
        if platform.system() == "Windows":
            chrome_options.add_argument("--disable-extensions")
        
        # Install ChromeDriver using webdriver_manager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    
    except Exception as e:
        st.error(f"Failed to setup Chrome WebDriver: {str(e)}")
        st.error("Please ensure Google Chrome is installed on your system.")
        sys.exit(1)

def wait_for_page_load(driver):
    """Wait for the page to fully load"""
    try:
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(2)  # Additional wait to ensure JavaScript has finished
    except TimeoutException:
        st.warning("Page load timeout - continuing anyway")

def scrape_current_page(driver, writer):
    """Scrape data from the current page"""
    # Wait for auction sections to be present
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CLASS_NAME, "Auct_Area"))
    )
    time.sleep(2)  # Additional wait for content to settle
    
    auction_sections = driver.find_elements(By.CLASS_NAME, "Auct_Area")
    rows_written = 0
    
    for section in auction_sections:
        auction_details = section.find_elements(By.CLASS_NAME, "AUCTION_DETAILS")
        if auction_details:
            for detail in auction_details:
                try:
                    # Wait for text content to be available
                    WebDriverWait(driver, 10).until(
                        lambda d: detail.text != ""
                    )
                    
                    lines = detail.text.splitlines()
                    if len(lines) < 8:  # Check if we have all required lines
                        continue
                        
                    row = {
                        "Case Status": lines[0].split(": ")[1] if len(lines) > 0 and ": " in lines[0] else "",
                        "Case #": lines[1].split(": ")[1] if len(lines) > 1 and ": " in lines[1] else "",
                        "Parcel ID": lines[2].split(": ")[1] if len(lines) > 2 and ": " in lines[2] else "",
                        "Property Address": lines[3].split(": ")[1] if len(lines) > 3 and ": " in lines[3] else "",
                        "City, ZIP": lines[4].strip() if len(lines) > 4 else "",
                        "Appraised Value": lines[5].split(": ")[1] if len(lines) > 5 and ": " in lines[5] else "",
                        "Opening Bid": lines[6].split(": ")[1] if len(lines) > 6 and ": " in lines[6] else "",
                        "Deposit Requirement": lines[7].split(": ")[1] if len(lines) > 7 and ": " in lines[7] else ""
                    }
                    writer.writerow(row)
                    rows_written += 1
                    
                    # Create a placeholder for progress updates if it doesn't exist
                    if 'progress_text' not in st.session_state:
                        st.session_state.progress_text = st.empty()
                    
                    # Update progress
                    st.session_state.progress_text.text(f"Processing Case #: {row['Case #']}")
                    
                except Exception as e:
                    st.warning(f"Error processing an auction detail: {str(e)}")
                    continue
    
    return rows_written

if run_button:
    try:
        with st.spinner("Initializing scraper..."):
            # Setup progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Initialize WebDriver
            driver = setup_webdriver()
            
            # Output CSV file path
            output_csv = 'auction_details.csv'
            
            # Define the headers for the CSV
            fieldnames = ["Case Status", "Case #", "Parcel ID", "Property Address", "City, ZIP", 
                         "Appraised Value", "Opening Bid", "Deposit Requirement"]
            
            # Format the date for the URL
            formatted_date = auction_date.strftime('%m/%d/%Y')
            url = f"https://franklin.sheriffsaleauction.ohio.gov/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={formatted_date}"
            
            status_text.text("Accessing auction website...")
            driver.get(url)
            wait_for_page_load(driver)  # Wait for initial page load
            
            # Wait for the content title to be present
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "Content_Title"))
            )
            
            # Initialize CSV file
            with open(output_csv, mode='w', newline='', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # Scrape first page
                status_text.text("Scraping page 1...")
                rows_written = scrape_current_page(driver, writer)
                
                # Handle pagination
                try:
                    # Wait for max pages element and ensure it has text
                    max_pages_text = wait_for_element_text(driver, By.ID, "maxWA")
                    if not max_pages_text:
                        raise ValueError("Could not determine maximum pages")
                    
                    max_pages = int(max_pages_text)
                    st.write(f"Total pages to scrape: {max_pages}")
                    
                    # Update progress bar
                    progress_bar.progress(1/max_pages)
                    
                    # Process remaining pages
                    current_page = 1
                    while current_page < max_pages:
                        current_page += 1
                        status_text.text(f"Scraping page {current_page} of {max_pages}...")
                        
                        # Navigate to next page
                        cur_page_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "curPWA"))
                        )
                        cur_page_input.clear()
                        cur_page_input.send_keys(str(current_page))
                        cur_page_input.send_keys("\n")
                        
                        # Wait for page load after navigation
                        wait_for_page_load(driver)
                        
                        # Scrape current page
                        rows_written += scrape_current_page(driver, writer)
                        
                        # Update progress
                        progress_bar.progress(current_page/max_pages)
                
                except Exception as e:
                    st.warning(f"Error during pagination: {str(e)}")
                    st.warning("Attempting to process available data...")
            
            # Clean up
            driver.quit()
            
            # Process the CSV file
            status_text.text("Processing data...")
            
            try:
                df = pd.read_csv(output_csv)
                
                if len(df) > 0:  # Only process if we have data
                    # Split City, ZIP and clean data
                    df[['City', 'ZIP']] = df['City, ZIP'].str.split(',', expand=True, n=1)
                    df['City'] = df['City'].str.strip()
                    df['ZIP'] = df['ZIP'].str.strip()
                    df = df.drop(columns=['City, ZIP'])
                    
                    # Format data
                    df['ZIP'] = df['ZIP'].str[:5]
                    df['Parcel ID'] = df['Parcel ID'].astype(str).str.zfill(9)
                    
                    # Save processed data
                    df.to_csv('auction_details.csv', index=False)
                    
                    # Display results
                    st.success(f"✅ Scraping completed! Total entries: {len(df)}")
                    st.dataframe(df)
                    
                    # Provide download button
                    st.download_button(
                        label="Download CSV",
                        data=df.to_csv(index=False).encode('utf-8'),
                        file_name='auction_details.csv',
                        mime='text/csv'
                    )
                else:
                    st.error("No data was scraped. Please check if the selected date has any auctions.")
                
            except Exception as e:
                st.error(f"Error processing CSV data: {str(e)}")
                st.error("Please check if any data was scraped successfully.")
            
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        if 'driver' in locals():
            driver.quit()
