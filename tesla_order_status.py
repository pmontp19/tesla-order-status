import base64
import json
import os
import time
import hashlib
import requests
import webbrowser
import urllib.parse

# Tesla's auth edge (Akamai) fingerprints the TLS handshake of the token request.
from curl_cffi import requests as tls_requests
TLS_IMPERSONATE = 'chrome'

from tesla_stores import TeslaStore

# Define constants
CLIENT_ID = 'ownerapi'
REDIRECT_URI = 'tesla://auth/callback'
AUTH_URL = 'https://auth.tesla.com/oauth2/v3/authorize'
TOKEN_URL = 'https://auth.tesla.com/oauth2/v3/token'
SCOPE = 'openid email offline_access'
CODE_CHALLENGE_METHOD = 'S256'
STATE = os.urandom(16).hex()
TOKEN_FILE = 'tesla_tokens.json'
ORDERS_FILE = 'tesla_orders.json'
APP_VERSION = '9.99.9-9999' # we can use a dummy version here, as the API does not check it strictly

# Option-code dictionary (verified against the community Tesla option-codes list).
# Highland codes IBB4/W38C/MT367 confirmed by the owner: Model 3 Standard RWD (base),
# 18" wheels and all-black interior (the standard/base configuration).
OPTION_CODES = {
    'MDL3': 'Model 3',
    'm3': 'Model 3',
    'MT367': 'Model 3 Standard RWD (base)',
    'PPSW': 'Blanc Perla multicapa (pintura)',
    'W38C': 'Rodes 18" (sèrie, Highland)',
    'IBB4': 'Interior tot negre (sèrie)',
    'APBS': 'Autopilot (inclòs)',
    'SC04': 'Supercharging Pay Per Use',
    'CPF0': 'Connectivitat estàndard (1 mes)',
    'CPF1': 'Connectivitat premium (1 any)',
    'MT300': 'Model 3 Standard Range RWD',
    'MT301': 'Model 3 Standard Range Plus RWD',
    'MT302': 'Model 3 Long Range RWD',
    'MT303': 'Model 3 Long Range AWD',
    'MT304': 'Model 3 Long Range AWD Performance',
    'IBB1': 'Interior tot negre',
    'IBW1': 'Interior blanc i negre',
    'W38A': 'Rodes 18" Photon (Highland)',
    'W39S': 'Rodes 19" Nova (Highland)',
    'W32P': 'Rodes 20" Performance',
    'DV2W': 'Traccio darrera (RWD)',
    'DV4W': 'Traccio total (AWD)',
}

def decode_options(mkt):
    decoded = []
    for code in (mkt or '').split(','):
        code = code.strip()
        if not code:
            continue
        decoded.append(OPTION_CODES.get(code, f'{code} (codi desconegut)'))
    return decoded

def color_text(text, color_code):
    return f"\033[{color_code}m{text}\033[0m"

def generate_code_verifier_and_challenge():
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode('utf-8')
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest()).rstrip(
        b'=').decode('utf-8')
    return code_verifier, code_challenge


def get_auth_code():
    auth_params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': SCOPE,
        'state': STATE,
        'code_challenge': code_challenge,
        'code_challenge_method': CODE_CHALLENGE_METHOD,
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(auth_params)}"
    print(color_text("> Opening the browser for authentication:", '94'), auth_url)
    webbrowser.open(auth_url)
    print(color_text("After logging in, the browser will try to redirect to a 'tesla://' URL which it cannot open.", '90'))
    print(color_text("Open your browser's Developer Tools (F12) → Network tab, find the redirect request, and copy the full 'tesla://auth/callback?code=...' URL from there.", '90'))
    redirected_url = input(color_text("Please enter the redirected URL here: ", '93'))
    parsed_url = urllib.parse.urlparse(redirected_url)
    return urllib.parse.parse_qs(parsed_url.query).get('code')[0]


def exchange_code_for_tokens(auth_code):
    token_data = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'code': auth_code,
        'redirect_uri': REDIRECT_URI,
        'code_verifier': code_verifier,
    }
    response = tls_requests.post(TOKEN_URL, data=token_data, impersonate=TLS_IMPERSONATE)
    response.raise_for_status()
    return response.json()


def save_tokens_to_file(tokens):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(tokens, f)
    print(color_text(f"> Tokens saved to '{TOKEN_FILE}'", '94'))


def load_tokens_from_file():
    with open(TOKEN_FILE, 'r') as f:
        return json.load(f)


def is_token_valid(access_token):
    jwt_decoded = json.loads(base64.b64decode(access_token.split('.')[1] + '==').decode('utf-8'))
    return jwt_decoded['exp'] > time.time()


def refresh_tokens(refresh_token):
    token_data = {
        'grant_type': 'refresh_token',
        'client_id': CLIENT_ID,
        'refresh_token': refresh_token,
    }
    response = tls_requests.post(TOKEN_URL, data=token_data, impersonate=TLS_IMPERSONATE)
    response.raise_for_status()
    return response.json()


def retrieve_orders(access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    api_url = 'https://owner-api.teslamotors.com/api/1/users/orders'
    response = requests.get(api_url, headers=headers)
    response.raise_for_status()
    return response.json()['response']


def get_order_details(order_id, access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    api_url = f'https://akamai-apigateway-vfx.tesla.com/tasks?deviceLanguage=es&deviceCountry=ES&referenceNumber={order_id}&appVersion={APP_VERSION}'
    response = requests.get(api_url, headers=headers)
    response.raise_for_status()
    return response.json()


def save_orders_to_file(orders):
    with open(ORDERS_FILE, 'w') as f:
        json.dump(orders, f)
    print(color_text(f"\n> Orders saved to '{ORDERS_FILE}'", '94'))


def load_orders_from_file():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, 'r') as f:
            return json.load(f)
    return None


def compare_dicts(old_dict, new_dict, path=''):
    differences = []
    for key in old_dict:
        if key not in new_dict:
            differences.append(color_text(f"- Removed key '{path + key}'", '91'))
        elif isinstance(old_dict[key], dict) and isinstance(new_dict[key], dict):
            differences.extend(compare_dicts(old_dict[key], new_dict[key], path + key + '.'))
        elif old_dict[key] != new_dict[key]:
            differences.append(color_text(f"- {path + key}: {old_dict[key]}", '91'))
            differences.append(color_text(f"+ {path + key}: {new_dict[key]}", '92'))

    for key in new_dict:
        if key not in old_dict:
            differences.append(color_text(f"+ Added key '{path + key}': {new_dict[key]}", '92'))

    return differences


def compare_orders(old_orders, new_orders):
    differences = []
    for i, old_order in enumerate(old_orders):
        if i < len(new_orders):
            differences.extend(compare_dicts(old_order, new_orders[i], path=f'Order {i}.'))
        else:
            differences.append(color_text(f"- Removed order {i}", '91'))
    for i in range(len(old_orders), len(new_orders)):
        differences.append(color_text(f"+ Added order {i}", '92'))
    return differences


# Main script logic
print(color_text("\n> Start retrieving the information. Please be patient...\n", '94'))

code_verifier, code_challenge = generate_code_verifier_and_challenge()

if os.path.exists(TOKEN_FILE):
    try:
        token_file = load_tokens_from_file()
        access_token = token_file['access_token']
        refresh_token = token_file['refresh_token']

        if not is_token_valid(access_token):
            print(color_text("> Access token is not valid. Refreshing tokens...", '94'))
            token_response = refresh_tokens(refresh_token)
            access_token = token_response['access_token']
            # refresh access token in file
            token_file['access_token'] = access_token
            save_tokens_to_file(token_file)

    except (json.JSONDecodeError, KeyError) as e:
        print(color_text("> Error loading tokens from file. Re-authenticating...", '94'))
        token_response = exchange_code_for_tokens(get_auth_code())
        access_token = token_response['access_token']
        refresh_token = token_response['refresh_token']
        save_tokens_to_file(token_response)
else:
    token_response = exchange_code_for_tokens(get_auth_code())
    access_token = token_response['access_token']
    refresh_token = token_response['refresh_token']
    if input(color_text("Would you like to save the tokens to a file in the current directory for use in future requests? (y/n): ", '93')).lower() == 'y':
        save_tokens_to_file(token_response)

old_orders = load_orders_from_file()
new_orders = retrieve_orders(access_token)

# Retrieve detailed order information
detailed_new_orders = []
for order in new_orders:
    order_id = order['referenceNumber']
    order_details = get_order_details(order_id, access_token)
    detailed_order = {
        'order': order,
        'details': order_details
    }
    detailed_new_orders.append(detailed_order)

if old_orders:
    differences = compare_orders(old_orders, detailed_new_orders)
    if differences:
        print(color_text("Differences found:", '90'))
        for diff in differences:
            print(diff)
        save_orders_to_file(detailed_new_orders)
    else:
        print(color_text("No differences found.", '90'))
    
else:
    # ask user if they want to save the new orders to a file for comparison next time
    if input(color_text("Would you like to save the order information to a file for future comparison? (y/n): ", '93')).lower() == 'y':
        save_orders_to_file(detailed_new_orders)

for detailed_order in detailed_new_orders:
    order = detailed_order['order']
    order_details = detailed_order['details']
    tasks = order_details.get('tasks', {})
    scheduling = tasks.get('scheduling', {})
    registration = tasks.get('registration', {})
    reg_data = registration.get('regData', {})
    final_payment = tasks.get('finalPayment', {})
    delivery_acceptance = tasks.get('deliveryAcceptance', {})
    financing = tasks.get('financing', {})
    trade_in = tasks.get('tradeIn', {})

    def g(d, *keys, default='N/A'):
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k)
            if cur is None or cur == '':
                return default
        return cur

    owner = f"{g(reg_data, 'owner', 'user', 'firstName')} {g(reg_data, 'owner', 'user', 'lastName')}"
    currency = g(final_payment, 'currencyFormat', 'currencyCode', default='EUR')
    amount_due = g(final_payment, 'amountDue')
    amount_sent = g(final_payment, 'amountSent')

    print(f"\n{'-'*55}")
    print(f"{'ORDER INFORMATION':^55}")
    print(f"{'-'*55}")

    print(f"{color_text('Comanda:', '94')}")
    print(f"{color_text('  Referència:', '94')} {order['referenceNumber']}")
    print(f"{color_text('  Estat:', '94')} {order['orderStatus']} ({order.get('orderSubstatus', '?')})")
    print(f"{color_text('  Model:', '94')} {OPTION_CODES.get(order.get('modelCode'), order.get('modelCode', 'N/A'))}")
    print(f"{color_text('  VIN:', '94')} {order.get('vin', 'N/A')}")

    print(f"\n{color_text('Configuració (opcions decodificades):', '94')}")
    for opt in decode_options(order.get('mktOptions')):
        print(f"{color_text('  -', '94')} {opt}")

    print(f"\n{color_text('Lliurament:', '94')}")
    print(f"{color_text('  Ubicació:', '94')} {g(scheduling, 'deliveryAddressTitle')}")
    print(f"{color_text('  Tipus:', '94')} {g(scheduling, 'deliveryType')}")
    print(f"{color_text('  Finestra:', '94')} {g(scheduling, 'deliveryWindowDisplay')}")
    print(f"{color_text('  Cita:', '94')} {g(scheduling, 'apptDateTimeAddressStr', default='Encara no assignada')}")
    print(f"{color_text('  ETA al centre:', '94')} {g(tasks, 'finalPayment', 'data', 'etaToDeliveryCenter', default='N/A')}")
    sched_url = g(scheduling, 'selfSchedulingUrl')
    sched_avail = 'Si' if scheduling.get('isSelfSchedulingAvailable') else 'No'
    print(f"{color_text('  Autoprogramació:', '94')} {sched_avail}  {sched_url if sched_url != 'N/A' else ''}")

    print(f"\n{color_text('Registre i finançament:', '94')}")
    print(f"{color_text('  Titular:', '94')} {owner}")
    print(f"{color_text('  Inici registre:', '94')} {g(reg_data, 'startedOn')} ({g(reg_data, 'startedBy')})")
    print(f"{color_text('  Tesla registra:', '94')} {g(reg_data, 'regDetails', 'isTeslaRegister')}")
    print(f"{color_text('  Tipus comanda:', '94')} {g(registration, 'orderType')}")
    print(f"{color_text('  Finançament:', '94')} {'confirmat' if financing.get('financeIntent') else 'no'} ({g(financing, 'status', default='?')})")
    print(f"{color_text('  Trade-in:', '94')} {g(trade_in, 'tradeInIntent')}")

    print(f"\n{color_text('Pagament final:', '94')}")
    print(f"{color_text('  Pendent:', '94')} {amount_due} {currency}  (pagat: {amount_sent})")
    print(f"{color_text('  Estat:', '94')} {g(final_payment, 'status')} ({'disponible' if final_payment.get('enabled') else 'pendent'})")

    print(f"\n{color_text('Estat de les tasques:', '94')}")
    for task_id in ['deliveryDetails', 'tradeIn', 'financing', 'registration', 'scheduling', 'finalPayment', 'deliveryAcceptance']:
        t = tasks.get(task_id, {})
        done = 'feta' if t.get('complete') else 'pendent'
        card = t.get('card', {}).get('title', '')
        print(f"{color_text('  - ' + task_id + ':', '94')} {done}" + (f"  ({card})" if card else ""))

    print(f"{'-'*55}\n")

