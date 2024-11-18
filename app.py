import streamlit as st
from playwright.sync_api import sync_playwright
import pandas as pd
import time

st.title("Auction Scraper - Handle 403 Forbidden")

auction_date = st.date_input("Select Auction Date")
run_button = st.button("Run Scraper")

def scrape_auctions(date):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False)  # Set to False for debugging
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://franklin.sheriffsaleauction.ohio.gov/"
                }
                # Uncomment below to add proxy
                # proxy={
                #     "server": "http://your-proxy-server.com:port",
                #     "username": "proxy-username",
                #     "password": "proxy-password"
                # }
            )
            page = context.new_page()

            formatted_date = date.strftime('%m/%d/%Y')
            url = f"https://franklin.sheriffsaleauction.ohio.gov/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={formatted_date}"

            # Attach response handler for debugging
            def handle_response(response):
                st.text_area("Response Info", f"Status: {response.status}\nURL: {response.url}")

            page.on("response", handle_response)

            # Navigate to the page
            page.goto(url)
            page.wait_for_load_state('networkidle')

            # Wait for additional loading
            time.sleep(10)

            # Locate auction details
            auction_details = page.locator('.AUCTION_DETAILS')
            count = auction_details.count()

            if count == 0:
                st.warning("No auctions found for the selected date.")
                return None

            # Extract data
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
                    except:
                        pass

                if auction_data:
                    data_list.append(auction_data)

            browser.close()
            return pd.DataFrame(data_list)

        except Exception as e:
            st.error(f"Error during scraping: {e}")
            return None

if run_button:
    df = scrape_auctions(auction_date)
    if df is not None:
        st.dataframe(df)
