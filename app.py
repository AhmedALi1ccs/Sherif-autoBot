import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller
import csv
import pandas as pd
import shutil


# Streamlit app header
st.title("Auction Scraper")
st.write("Press the button to scrape auction details. The app will handle everything for you.")

# User input for auction date
auction_date = st.date_input("Select Auction Date")
run_button = st.button("Run Scraper")

if run_button:
    st.write("Initializing scraper...")

    try:
        # Automatically install ChromeDriver
        chromedriver_autoinstaller.install()

        # Locate the Chromium binary
        chrome_binary_path = shutil.which("chromium-browser") or shutil.which("google-chrome")
        if not chrome_binary_path:
            raise FileNotFoundError("Chromium or Google Chrome is not installed.")

        # Set Chrome options for headless mode
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.binary_location = chrome_binary_path

        # Initialize WebDriver
        driver = webdriver.Chrome(options=chrome_options)

        # Define output CSV file and column headers
        output_csv = "auction_details.csv"
        fieldnames = [
            "Case Status",
            "Case #",
            "Parcel ID",
            "Property Address",
            "City, ZIP",
            "Appraised Value",
            "Opening Bid",
            "Deposit Requirement",
        ]

        # Function to scrape data from the current page
        def scrape_current_page(writer):
            auction_sections = driver.find_elements_by_class_name("Auct_Area")
            for section in auction_sections:
                auction_details = section.find_elements_by_class_name("AUCTION_DETAILS")
                for detail in auction_details:
                    lines = detail.text.splitlines()
                    row = {
                        "Case Status": lines[0].split(": ")[1] if "Case Status" in lines[0] else "",
                        "Case #": lines[1].split(": ")[1] if "Case #" in lines[1] else "",
                        "Parcel ID": lines[2].split(": ")[1] if "Parcel ID" in lines[2] else "",
                        "Property Address": lines[3].split(": ")[1] if "Property Address" in lines[3] else "",
                        "City, ZIP": lines[4].strip() if "," in lines[4] else "",
                        "Appraised Value": lines[5].split(": ")[1] if "Appraised Value" in lines[5] else "",
                        "Opening Bid": lines[6].split(": ")[1] if "Opening Bid" in lines[6] else "",
                        "Deposit Requirement": lines[7].split(": ")[1] if "Deposit Requirement" in lines[7] else "",
                    }
                    writer.writerow(row)

        # Navigate to the auction page
        url = f"https://franklin.sheriffsaleauction.ohio.gov/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date.strftime('%m/%d/%Y')}"
        driver.get(url)

        # Open the CSV file and write headers
        with open(output_csv, mode="w", newline="", encoding="utf-8") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            scrape_current_page(writer)  # Scrape the first page

        # Display success message and data
        st.success("Scraping completed successfully!")
        st.write(f"Data saved to `{output_csv}`.")

        # Read and display the CSV file in Streamlit
        df = pd.read_csv(output_csv)
        st.dataframe(df)

    except Exception as e:
        st.error(f"An error occurred: {e}")

    finally:
        # Ensure the WebDriver quits properly
        try:
            if 'driver' in locals():
                driver.quit()
        except Exception as e:
            st.warning(f"Error closing the WebDriver: {e}")
