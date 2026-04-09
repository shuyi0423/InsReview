import requests
response = requests.get(url="https://devmatrix.qtech.cn/api/providerOrg/sync/init/internalApp?appId=cli_a7f12e062f751013&appSecret=hi2lcacnrscYK2L5OUNZve1mb6qHqVtD&token=Bmy4d9KbGo3RBkxEqg7cSUGUnNd&keyName=shuyi01&appName=智书企飞&seatCount=9999&appKey=shuyi01")
print(response.text)