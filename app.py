import requests
from requests_aws4auth import AWS4Auth

AWS_ACCESS_KEY = "YOUR_AWS_KEY"
AWS_SECRET_KEY = "YOUR_AWS_SECRET"
AWS_REGION = "eu-west-1"

auth = AWS4Auth(
    AWS_ACCESS_KEY,
    AWS_SECRET_KEY,
    AWS_REGION,
    "execute-api"
)

url = "https://sellingpartnerapi-eu.amazon.com/sellers/v1/marketplaceParticipations"

response = requests.get(url, auth=auth)

print(response.status_code)
print(response.text)
