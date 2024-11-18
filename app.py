import streamlit as st
from playwright.sync_api import sync_playwright
import pandas as pd
import time

# Streamlit interface
st.title("Auction Scraper - Increased Delay")

auction_date = st.date_input("Select Auction Date")
run_button = st.button("Run Scraper")

def scrape_auctions(date):
    """Scrapes auction data from the page with increased delay."""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)  # Use headless=True for deployment
            context = browser.new_context()
            page = context.new_page()

            # Format the date for the URL
            formatted_date = date.strftime('%m/%d/%Y')
            url = f"https://franklin.sheriffsaleauction.ohio.gov/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={formatted_date}"

            # Navigate to the page
            page.goto(url)
            page.wait_for_load_state('networkidle')

            # Increase delay for additional loading time
            time.sleep(10)  # Adjust if needed

            # Locate auction details
            auction_details = page.locator('.AUCTION_DETAILS')
            count = auction_details.count()

            if count == 0:
                st.warning("No auctions found for the selected date.")
                return None

            # Extract data from each auction detail block
            data_list = []
            for i in range(count):
                table_rows = auction_details.nth(i).locator('table.ad_tab tr')
                row_count = table_rows.count()

                auction_data = {}
                for j in range(row_count):
                    try:
                        label = table_rows.nth(j).locator('th.AD_LBL').inner_text().strip(":")
                        value = table_rows.nth(j).locator('td.AD_DTA').inner_text().strip()
                        auction_data[label] = value
                    except Exception as e:
                        st.warning(f"Error extracting row {j + 1} in auction {i + 1}: {e}")

                # Append cleaned data
                if auction_data:
                    data_list.append({
                        "Case Status": auction_data.get("Case Status", ""),
                        "Case #": auction_data.get("Case #", ""),
                        "Parcel ID": auction_data.get("Parcel ID", ""),
                        "Property Address": auction_data.get("Property Address", ""),
                        "City, ZIP": auction_data.get("", ""),  # Empty label for City, ZIP
                        "Appraised Value": auction_data.get("Appraised Value", ""),
                        "Opening Bid": auction_data.get("Opening Bid", ""),
                        "Deposit Requirement": auction_data.get("Deposit Requirement", "")
                    })

            browser.close()
            return pd.DataFrame(data_list)

        except Exception as e:
            st.error(f"Error during scraping: {e}")
            return None

if run_button:
    st.info("Starting the scraping process...")
    df = scrape_auctions(auction_date)

    if df is not None and not df.empty:
        try:
            # Split City, ZIP and clean data
            df[['City', 'ZIP']] = df['City, ZIP'].str.split(',', expand=True)
            df['City'] = df['City'].str.strip()
            df['ZIP'] = df['ZIP'].str.strip()
            df = df.drop(columns=['City, ZIP'])

            # Display results
            st.success(f"✅ Scraping completed! Total entries: {len(df)}")
            st.dataframe(df)

            # Provide download button
            st.download_button(
                label="Download CSV",
                data=df.to_csv(index=False).encode('utf-8'),
                file_name=f'auction_details_{auction_date.strftime("%Y%m%d")}.csv',
                mime='text/csv'
            )

        except Exception as e:
            st.error(f"Error processing data: {e}")
