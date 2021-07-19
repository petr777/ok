from flask import Flask
from flask_restful import Resource, Api, reqparse
import asyncio
from scrapy import Selector
import re
import os
import httpx
from urllib.parse import urlparse
from dotenv import load_dotenv


load_dotenv()


def get_cookies():
    client = httpx.Client()
    headers = {
            'User-Agent': os.getenv('USER_AGENT')
    }
    client.get('https://ok.ru/', headers=headers)
    data = {
            'st.redirect': "",
            'st.asr': "",
            'st.posted': 'set',
            'st.fJS': 'on',
            'st.st.screenSize': '1920 x 1080',
            'st.st.browserSize': '467',
            'st.st.flashVer': '0.0.0',
            'st.email': os.getenv('USER_OK'),
            'st.password': os.getenv('PASS_OK'),
            'st.iscode': 'False',
    }
    client.post(
            'https://ok.ru/dk?cmd=AnonymLogin&st.cmd=anonymLogin',
            headers=headers,
            data=data
        )
    client.close()
    return client.cookies


def user_page(id_user, headers, cookies, timeout=60):
    client = httpx.Client(
        headers=headers,
        cookies=cookies,
    )
    r = client.get(
        f'https://ok.ru/profile/{id_user}/friends',
        timeout=timeout
    )
    if r.status_code == 200:
        page = Selector(text=r.text)
        total_friends = page.xpath('//span[@class="lstp-t"]/span/text()').get()
        total_friends = total_friends.replace(u'\xa0', '')
        total_page = int(total_friends)//21 + 1
        patern = "OK.tkn.set\('(.*?)'\);"
        tkn = re.findall(patern, page.get())[0]
        return tkn, total_page
    return None, None


async def main(args):
    all_user = []

    async def eternity(limit):
        cookies = app.config['cookies']
        headers = {'User-Agent': os.getenv('USER_AGENT')}

        tkn, total_page = user_page(
            args.id,
            headers,
            cookies,
            timeout=args.timeout
        )

        def get_user(r):
            page = Selector(text=r.text)
            for user in page.xpath('//div[@class="ugrid_i"]'):
                item = {}
                item['_id'] = user.xpath('./div/@data-entity-id').get()

                o = urlparse(user.xpath('.//a[@class="o"]/@href').get())
                if str(item['_id']) not in o.path:
                    item['alias'] = o.path.replace('/', '')
                else:
                    item['alias'] = None

                item['name'] = user.xpath('.//a[@class="o"]/text()').get()
                photo_img = user.xpath('.//img[@class="photo_img"]/@src').get()
                if photo_img:
                    photo_img = 'http:' + photo_img
                item['photo_img'] = photo_img
                all_user.append(item)

        async def fetch(data):
            async with httpx.AsyncClient() as async_client:
                url = f'https://ok.ru/dk?st.cmd=friendFriend&st.friendId={args.id}&cmd=FriendsPageMRB'

                async_client.headers = headers
                async_client.cookies = cookies
                async_client.timeout = 60
                async_client.headers.update({'tkn': tkn})

                r_friends = await async_client.post(url, data=data)
                get_user(r_friends)

        async def bound_fetch(sem, data):
            async with sem:
                await fetch(data)

        tasks = []

        sem = asyncio.Semaphore(int(os.getenv('SEMAPHORE')))
        count_frinds = 0

        for num_page in range(1, total_page + 1):
            count_frinds += 21
            data = {
                'fetch': 'false',
                'st.page': num_page,
                'gwt.requested': '4c3ab235T1625649727652',
            }

            task = asyncio.ensure_future(bound_fetch(sem, data))
            tasks.append(task)
            # Ограничиваем кол-во tasks по limit
            if limit and count_frinds >= limit:
                break

        responses = asyncio.gather(*tasks)
        await responses

    try:
        await asyncio.wait_for(eternity(args.limit), timeout=args.timeout)
    finally:
        return all_user[:args.limit]


class OK_API(Resource):

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument(
            'id',
            type=int,
            required=True,
            help="id cannot be blank!"
        )

        parser.add_argument('limit', type=int)
        parser.add_argument('timeout', type=int)
        args = parser.parse_args()

        if args.timeout is None:
            args.timeout = 60

        data = loop.run_until_complete(main(args))
        return {'result': data}

app = Flask(__name__)
app.config['cookies'] = get_cookies()
api = Api(app)
api.add_resource(OK_API, '/ok/friends')


loop = asyncio.get_event_loop()

if __name__ == '__main__':
    app.run(host='0.0.0.0')
