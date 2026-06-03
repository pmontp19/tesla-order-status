## Installation

To run the script, you need to install python3 for your operating system.

https://www.python.org/downloads/

Then you need to install the `requests` library by running:
```sh
pip install requests
```

Optional: Copy the script to a new directory, the script asks to save the tokens and order details in the current directory for reusing the tokens and for comparing the data with the last time you fetched the order details.

Then you can run the script by running:
```sh
python3 tesla_order_status.py
```

## How to authenticate / login

When you run the script for the first time, it will open your browser to log in with your Tesla account. Since the redirect URL uses a `tesla://` protocol that browsers can't open, you need to grab the URL from your browser's Developer Tools. Here's how:

1. Run the script — it will open the Tesla login page in your browser.
2. Log in with your Tesla account credentials.
3. After logging in, the browser will try to redirect to a `tesla://` URL. The page will show an error or a blank page — this is expected.
4. Open your browser's **Developer Tools** (press `F12` or `Cmd+Option+I` on macOS), go to the **Console** tab, and find the redirect request that starts with `tesla://auth/callback?code=...`. Copy the full URL.

![Copying the URL from the browser console](https://github.com/user-attachments/assets/518b827b-9bf4-4f61-bfa4-0c9c8a0a00ab)

5. Paste the copied URL back into the terminal where the script is waiting for input, and press Enter.

![Pasting the URL in the terminal](https://github.com/user-attachments/assets/68a97d8b-5167-4732-a239-b2afaa7e0ff2)

The script will exchange the code for access tokens and save them locally in `tesla_tokens.json` for future use. You won't need to log in again until the tokens expire.

## Preview

#### Main information
![Image](https://github.com/user-attachments/assets/b19cf27c-e3a3-48a0-9b7f-ec2c649e4166)

#### Change tracking
![Image](https://github.com/user-attachments/assets/4f1f05cb-743e-4605-97ff-3c1d0d6ff67d)

