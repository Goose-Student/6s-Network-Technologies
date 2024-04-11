import os.path
from os.path import exists as is_exists
from socket import AF_INET, SOCK_STREAM
from threading import Thread

from common.network import Socket, Headers, Messages


class Handler(Thread):
    """
    Класс, представляющий обработчик соединения.

    Класс управляет текущим состоянием соединения и обрабатывает запросы от клиента.
    """

    def __init__(self, socket: Socket):
        """
        Инициализация объекта Handler.

        Args:
            socket (Socket): Объект socket.
        """
        super().__init__()
        # Внешние атрибуты
        self._socket = socket

        # Внутренние атрибуты
        self._state = self.connect

    def run(self):
        try:
            while self._state:
                self._state()
        except (TimeoutError, ConnectionAbortedError) as exception:
            print(f"ERR: '{exception}'. Connection close.")
            self._socket.close()

    def connect(self) -> None:
        """
        Метод для установления соединения с сервером.

        Пользователь выбирает метод (аутентификация или регистрация) и версию протокола.
        """
        user_agent = b'Python3 Client Win64'
        method = input('Введите метод (<auth> или <reg>): ').strip().encode()
        version = input('Введите версию (<1> или <2>): ').strip().encode()

        self._socket.send(Headers.CONN, user_agent, method, version)
        msgs = self._socket.receive(target_len=2)

        # Проверка корректности запроса
        if msgs[1] == Messages.CONN_ERR:
            self._state = None
            return print(msgs[1].decode())
        elif msgs[1] != Messages.CONN_SUC:
            return print(msgs[1].decode())

        # Определение метода
        if method == Headers.AUTH:
            self._state = self.auth
        elif method == Headers.REG:
            self._state = self.reg
        return print(msgs[1].decode())

    def auth(self):
        """
        Метод для аутентификации пользователя.

        Пользователь вводит логин и пароль, затем отправляет их для аутентификации на сервере.
        """
        login = input('Введите логин: ').strip().encode()
        password = input('Введите пароль: ').strip().encode()

        self._socket.send(Headers.AUTH, login, password)
        msgs = self._socket.receive(target_len=2)

        if msgs[1] != Messages.AUTH_SUC:
            return print(msgs[1].decode())

        self._state = self.upload
        return print(msgs[1].decode())

    def reg(self):
        """
        Метод для регистрации нового пользователя.

        Пользователь вводит логин и пароль, затем отправляет их для регистрации на сервере.
        """
        login = input('Введите логин: ').strip().encode()
        password = input('Введите пароль: ').strip().encode()

        self._socket.send(Headers.REG, login, password)
        msgs = self._socket.receive(target_len=2)

        if msgs[1] != Messages.REG_SUC:
            return print(msgs[1].decode())

        self._state = self.upload
        return print(msgs[1].decode())

    def upload(self):
        """
        Метод для загрузки файла на сервер.

        Пользователь вводит путь к файлу, который затем отправляется на сервер.
        """
        path = input('Введите путь: ').strip()
        path = path.replace('"', '').replace("'", "")
        if not is_exists(path):
            return print(f"LocalERR: файл {path} не существует")

        fileName = os.path.basename(path).encode()
        with open(path, 'rb') as file:
            content = file.read()

        self._socket.send(Headers.UP, fileName, content)
        msgs = self._socket.receive(target_len=2)

        if msgs[1] != Messages.UP_SUC:
            return print(msgs[1].decode())

        self._state = None
        return print(msgs[1].decode())


client_socket = Socket(AF_INET, SOCK_STREAM)
client_socket.settimeout(60)
client_socket.connect(('127.0.0.1', 25565))
handler = Handler(client_socket)
handler.start()
