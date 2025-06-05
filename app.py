import streamlit as st
from playwright.sync_api import sync_playwright
import pandas as pd
import time
import os

# Install Playwright browsers (required for deployment)
os.system("playwright install chromium")

# Streamlit App Title
st.title("Auction Scraper - Multi-Page Support")

# User Input for Auction Date
st.subheader("Enter the Auction Date")
auction_date = st.date_input("Select Auction Date")
run_button = st.button("Run Scraper")

# Function to Scrape Auctions
def scrape_auctions(date):
    """Scrapes auction data from the specified date, including all pages."""
    with sync_playwright() as p:
        try:
            # Launch browser in headless mode
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://franklin.sheriffsaleauction.ohio.gov/"
                }
            )
            page = context.new_page()

            # Format the date for the URL
            formatted_date = date.strftime('%m/%d/%Y')
            url = f"https://franklin.sheriffsaleauction.ohio.gov/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={formatted_date}"
            
            # Inform the user about the scraping process
            st.info(f"Scraping auction data for date: {formatted_date}")

            # Navigate to the first page
            page.goto(url)
            page.wait_for_load_state('networkidle')

            # Additional delay to allow dynamic content to load
            time.sleep(5)

            # Find the total number of pages
            max_pages_element = page.locator("#maxWA")
            if max_pages_element.count() == 0:
                st.warning("Could not determine the total number of pages.")
                return None
            max_pages = int(max_pages_element.inner_text().strip())
            st.info(f"Total pages to scrape: {max_pages}")

            # Initialize data storage
            data_list = []

            # Loop through all pages
            for current_page in range(1, max_pages + 1):
                st.info(f"Scraping Page {current_page} of {max_pages}...")

                # Locate auction details
                auction_details = page.locator('.AUCTION_DETAILS')
                count = auction_details.count()

                if count == 0:
                    st.warning(f"No auctions found on Page {current_page}.")
                    break

                # Progress Bar for Feedback
                progress_bar = st.progress(0)

                # Extract data from each auction detail block
                for i in range(count):
                    table_rows = auction_details.nth(i).locator('table.ad_tab tr')
                    row_count = table_rows.count()

                    auction_data = {}
                    for j in range(row_count):
                        try:
                            label = table_rows.nth(j).locator('th.AD_LBL').inner_text().strip(":")
                            value = table_rows.nth(j).locator('td.AD_DTA').inner_text().strip()
                            auction_data[label] = value
                        except:
                            continue

                    # Properly extract 'Auction Starts'
                    try:
                        auction_starts_locator = page.locator('.AUCTION_STATS .ASTAT_MSGB').nth(i)
                        auction_starts = auction_starts_locator.inner_text().strip()
                    except:
                        auction_starts = ""

                    # Append cleaned data including 'Auction Starts'
                    data_list.append({
                        "Case Status": auction_data.get("Case Status", ""),
                        "Case #": auction_data.get("Case #", ""),
                        "Parcel ID": auction_data.get("Parcel ID", ""),
                        "Property Address": auction_data.get("Property Address", ""),
                        "City, ZIP": auction_data.get("", ""),
                        "Appraised Value": auction_data.get("Appraised Value", ""),
                        "Opening Bid": auction_data.get("Opening Bid", ""),
                        "Deposit Requirement": auction_data.get("Deposit Requirement", ""),
                        "Auction Starts": auction_starts
                    })

                    # Update progress bar
                    progress_bar.progress((i + 1) / count)



                # Move to the next page if not on the last page
                if current_page < max_pages:
                    current_page_input = page.locator("#curPWA")
                    current_page_input.fill(str(current_page + 1))  # Update the input value to the next page
                    current_page_input.press("Enter")  # Simulate pressing Enter to navigate to the next page
                    time.sleep(5)  # Allow time for the next page to load

            browser.close()
            return pd.DataFrame(data_list)

        except Exception as e:
            st.error(f"Error during scraping: {e}")
            return None

# Run Scraper if Button is Pressed
if run_button:
    st.info("Starting the scraping process...")
    df = scrape_auctions(auction_date)

    if df is not None and not df.empty:
        # Split and Clean Data
        df[['City', 'ZIP']] = df['City, ZIP'].str.split(',', expand=True)
        df['City'] = df['City'].str.strip()
        df['ZIP'] = df['ZIP'].str.strip()
        df = df.drop(columns=['City, ZIP'])
        df['ZIP'] = df['ZIP'].str[:5]
        # Display Results
        st.success(f"✅ Scraping completed! Total entries: {len(df)}")
        st.dataframe(df)

        # Download Button
        st.download_button(
            label="Download CSV",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name=f'auction_details_{auction_date.strftime("%Y%m%d")}.csv',
            mime='text/csv'
        )
    else:
        st.warning("No data available for the selected date.")
