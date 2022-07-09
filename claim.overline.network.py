import secrets
import asyncio
import aiohttp
import aiofiles
from pyuseragents import random as random_useragent
from loguru import logger
from sys import stderr, exit, platform
from random import choice, randint
from capmonster_python import RecaptchaV2Task, CapmonsterException
from json import loads
from imap_tools import MailBox, AND
from time import sleep
from string import ascii_letters, digits
from multiprocessing.dummy import Pool
from threading import Thread, active_count
from aiohttp_proxy import ProxyConnector
from os.path import exists
from os import system


class Wrong_Response(Exception):
    pass


class Email_Timeout(Exception):
    pass


headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'ru,en;q=0.9,vi;q=0.8,es;q=0.7',
    'content-type': 'application/json',
    'origin': 'https://claim.overline.network',
    'referer': 'https://claim.overline.network'
}


logger.remove()
logger.add(stderr, format="<white>{time:HH:mm:ss}</white>"
                          " | <level>{level: <8}</level>"
                          " | <cyan>{line}</cyan>"
                          " - <white>{message}</white>")


def random_file_proxy():
    with open(proxy_folder, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    proxy_str = f'{proxy_type}://' + choice(lines)

    return(proxy_str)


def random_tor_proxy():
    proxy_auth = str(randint(1, 0x7fffffff))\
                 + ':'\
                 + str(randint(1, 0x7fffffff))
    proxies = f'socks5://{proxy_auth}@localhost:' + str(choice(tor_ports))
    return(proxies)


def random_string(length):
    return("".join([choice("abcdefghijklmnopqrstuvwxyz"
                           "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                           "0123456789")
                    for _ in range(length)]))


def random_password(length):
    alphabet = ascii_letters + digits
    while True:
        password = ''.join(secrets.choice(alphabet) for i in range(length))

        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and sum(c.isdigit() for c in password) >= 1):

            return(password)


def solve_captcha():
    task_id = capmonster.create_task("https://claim.overline.network",
                                     "6LcgKYcgAAAAADOtljPjac6iL3upVCwJwR3fEYn2")
    result = capmonster.join_task_result(task_id)
    captcha_response = result.get("gRecaptchaResponse")
    return(captcha_response)


class App:
    def __init__(self, email, password):
        if user_work_type == 1:
            self.email = email

        else:
            self.email = email.split('@')[0] + '+'\
                + random_string(15) + '@'\
                + email.split('@')[-1]

        self.password = password
        self.account_password = random_password(15)

    async def get_connector(self):
        if use_proxy:
            if proxy_source == 1:
                connector = ProxyConnector.from_url(random_tor_proxy())

            else:
                connector = ProxyConnector.from_url(random_file_proxy())

        else:
            connector = None

        return(connector)

    async def Register_Account(self, session):
        while True:
            try:
                captcha_response = solve_captcha()

            except CapmonsterException as error:
                logger.error(f'{self.email} | Ошибка при решении капчи: {error}')

            else:
                break

        r = await session.post('https://claim.overline.network/api/v1/account/subscribe',
                               json={
                                   'affiliateToken': ref_code,
                                   'captcha': captcha_response,
                                   'email': self.email
                               })

        if not loads(str(await r.text())).get('status')\
                or loads(str(await r.text()))['status'] != 'ok':
            raise Wrong_Response(str(await(r.text())))

        logger.success(f'{self.email} | Регистрация прошла успешно, '
                       'ожидаю письма')

    def Get_Verify_Link(self):
        with MailBox(imap_protocol).login(self.email,
                                             self.password) as mailbox:
            for _ in range(12):
                sleep(5)
                for msg in mailbox.fetch(AND(to=self.email,
                                             from_=('hello@overline.network'))):

                    if len(msg.text) > 0\
                            and 'Land NFT Waitlist - Please Verify Your Email'\
                                in msg.subject:
                        return(msg.text.split('your web browser:')[-1]
                                       .split('If you did not create an account')[0]
                                       .replace(' ', '')
                                       .strip())

            raise Email_Timeout()

    async def Enter_Password(self, session, url):
        verificationToken = url.split('initializationToken=')[-1]

        r = await session.post('https://claim.overline.network/api/v1/account/initialize',
                               json={
                                   'password': self.account_password,
                                   'verificationToken': verificationToken
                               })

        if not loads(str(await r.text())).get('status')\
                or loads(str(await r.text()))['status'] != 'ok':
            raise Wrong_Response(str(await r.text()))

    async def Create_Client(self):
        async with aiohttp.ClientSession(
                                        headers={
                                            **headers,
                                            'user-agent': random_useragent()
                                        },
                                        connector=await self.get_connector()
                                        ) as session:
            try:
                await self.Register_Account(session)

            except Wrong_Response as error:
                logger.error(f'{self.email} | Неверный ответ при регистрации аккаунта, '
                             f'текст ответа: {error}')
                return

            except Exception as error:
                logger.error(f'{self.email} | Неизвестная ошибка при регистрации аккаунта, '
                             f'{error}')

                return

            try:
                verify_link = self.Get_Verify_Link()

            except Email_Timeout:
                logger.error(f'{self.email} | Не удалось дождаться письма')

                return

            except Exception as error:
                logger.error(f'{self.email} | Неизвестная ошибка при ожидании письма, '
                             f'{error}')

                return

            try:
                await self.Enter_Password(session, verify_link)

            except Wrong_Response as error:
                logger.error(f'{self.email} | Неверный ответ при подтверждении аккаунта, '
                             f'текст ответа: {error}')

                return

            except Exception as error:
                logger.error(f'{self.email} | Неизвестная ошибка при подтверждении аккаунта, '
                             f'{error}')

                return

            else:
                logger.success(f'{self.email} | Аккаунт успешно зарегистрирован')

                async with aiofiles.open('registered.txt', 'a') as file:
                    await file.write(f'{self.email}:{self.account_password}\n')
                    await file.flush()


def wrapper(data):
    global progress

    asyncio.run(App(data.split(':')[0],
                    data.split(':')[-1]).Create_Client())

    progress += 1
    system(f'title claim.overline.network Auto Reger // Progress: {progress}')


if __name__ == '__main__':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    progress = 0
    system(f'title claim.overline.network Auto Reger // Progress: {progress}')

    if exists('tor_ports.txt'):
        with open('tor_ports.txt', 'r', encoding='utf-8') as file:
            tor_ports = [row.strip() for row in file]

    else:
        tor_ports = [9150]

    threads = int(input('Введите количество потоков: '))
    capmonster = RecaptchaV2Task(input('Введите Api Key от capmonster: '))
    ref_link = input('Введите вашу реф.ссылку: ')
    ref_code = ref_link.split('?affiliateToken=')[-1]
    use_proxy = input('Использовать Proxy? (y/N): ').lower()

    if use_proxy == 'y':
        use_proxy = True

        proxy_source = int(input('Источник прокси (1 - tor proxies; '
                                 '2 - from .txt): '))

        if proxy_source == 2:
            proxy_type = input('Введите тип прокси (http; socks4; socks5): ')
            proxy_folder = input('Перетяните .txt с Proxy (user:pass@ip:port // ip:port): ')

    else:
        use_proxy = False

    user_work_type = int(input('1. Прогнать свои почты (email:pass)\n'
                               '2. Регистрировать на основную Gmail почту\n'
                               'Выберите режим работы: '))

    if user_work_type == 1:
        emails_folder = str(input('Перетяните .txt с почтами: '))

        with open(emails_folder, 'r', encoding='utf-8') as file:
            emails = [row.strip() for row in file]

        imap_protocol = input('Введите адрес IMAP вашего почтового сервиса: ')

        system('cls')

        with Pool(processes=threads) as executor:
            executor.map(wrapper, emails)

    elif user_work_type == 2:
        email_user = input('Введите вашу @gmail почту: ')
        email_password = input('Введите пароль ПРИЛОЖЕНИЯ от почты: ')

        system('cls')

        imap_protocol = 'imap.gmail.com'

        while True:
            if active_count() < threads + 1:
                Thread(target=wrapper, args=(f'{email_user}:{email_password}', )).start()

    logger.success('Работа успешно завершена')

    if platform == 'win32':
        from msvcrt import getch

        print('\nНажмите любую клавишу для выхода...')
        getch()

    else:
        print('\nНажмите Enter для выхода...')
        input()

    exit()
