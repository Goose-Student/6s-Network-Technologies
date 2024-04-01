from os.path import exists as is_exists
import pickle
from socket import AF_INET, SOCK_STREAM
from threading import Thread
from typing import Tuple, List

from common.network import Socket, Hs, Ms

PATH = './workgroup.bin'
HOST = ''
PORT = 25565
CONN_LIMIT = 3


def file_type(content: bytes) -> bytes:
    """
    Определить тип файла на основе содержимого.

    Args:
        content (bytes): Содержимое файла.

    Returns:
        bytes: Идентификатор типа файла ('1' для текстового, '2' для двоичного).
    """
    try:
        content.decode()
        return b'1'  # Текстовый тип файла
    except UnicodeDecodeError:
        return b'2'  # Бинарный тип файла


class Data(dict):
    """
    Пользовательский класс данных для управления серверными данными.
    """

    def __init__(self, path: str = './workgroup.bin'):
        """
        Инициализация объекта Data.

        Args:
            path (str): Путь к файлу данных.
        """
        self._path = path
        if is_exists(path):  # Проверка, существует ли файл
            file = open(path, 'rb')
            try:
                super().__init__(pickle.load(file))  # Загрузка данных из файла
                file.close()
                return
            except EOFError:
                file.close()
        super().__init__({'whitelist': ['127.0.0.1'], 'users': {}})  # Данные по умолчанию, если файл не существует
        with open(path, 'wb+') as file:
            pickle.dump(self, file)  # Сохранение данных в файле

    def commit(self):
        """
        Фиксация данных в файле.
        """
        with open(self._path, 'wb+') as file:
            pickle.dump(self, file)  # Update and store data to the file


class Handler(Thread):
    """
    Пользовательский класс для обработки клиентских подключений.
    """

    def __init__(self, socket: Socket, address: Tuple, data: Data, queue: List['Handler']):
        """
        Инициализация объекта обработчика

        Args:
            socket (Socket): Объект socket.
            address (Tuple): Информация об адресе.
            data (Data): Объект данных сервера.
            queue (List): Список с активными обработчиками.
        """
        super().__init__()
        # Внешние атрибуты
        self._socket = socket
        self._data = data

        # Собственные атрибуты
        self._state = self.connect
        self._version = None

        # Setup
        self._exit_flag = not (address[0] in data['whitelist'] and len(queue) < CONN_LIMIT)

    def run(self):
        """
        Запуск потока обработчика.
        """
        try:
            while self._state:
                self._state()
        except (TimeoutError, ConnectionAbortedError) as exception:
            print(f"ERR: '{exception}'. Connection close.")
            self._socket.close()

    # Состояние подключения
    def connect(self) -> None:
        """
        Обработка состояния подключения.
        """
        msgs = self._socket.receive(target_len=4)

        if self._exit_flag:
            self._state = None
            return self._socket.send(Hs.CONN, Ms.CONN_ERR)

        isHeader = (msgs[0] == Hs.CONN)
        isMethod = msgs[2] in (Hs.AUTH, Hs.REG)
        isVersion = msgs[3] in (b'1', b'2')

        if not (isHeader and isVersion and isMethod):
            return self._socket.send(Hs.CONN, Ms.REQ_ERR)

        self._socket.send(Hs.CONN, Ms.CONN_SUC)
        self._state = self.auth if msgs[2] == Hs.AUTH else self.reg
        self._version = msgs[3]

    def auth(self):
        """
        Обработка состояния аутентификации.
        """
        msgs = self._socket.receive(target_len=3)

        isHeader = (msgs[0] == Hs.AUTH)
        isValid = (msgs[1] in self._data['users'] and self._data['users'][msgs[1]] == msgs[2])

        if not isHeader:
            return self._socket.send(Hs.AUTH, Ms.REQ_ERR)
        elif not isValid:
            return self._socket.send(Hs.AUTH, Ms.AUTH_ERR)

        self._socket.send(Hs.AUTH, Ms.AUTH_SUC)
        self._state = self.upload

    def reg(self):
        """
        Обработать состояние регистрации нового пользователя.
        """
        msgs = self._socket.receive(target_len=3)

        isHeader = (msgs[0] == Hs.REG)
        isUser = not (msgs[1] in self._data['users'] or msgs[1] == b'@null')
        isPass = not (msgs[2] == b'@null')

        if not isHeader:
            return self._socket.send(Hs.REG, Ms.REQ_ERR)
        elif not (isUser and isPass):
            return self._socket.send(Hs.REG, Ms.REG_ERR)

        self._data['users'][msgs[1]] = msgs[2]
        self._data.commit()

        self._socket.send(Hs.REG, Ms.REG_SUC)
        self._state = self.upload

    def upload(self):
        """
        Обработка состояния загрузки файла.
        """
        msgs = self._socket.receive(target_len=3)

        isHeader = (msgs[0] == Hs.UP)
        isFileName = not (msgs[1] == b'\null')
        isContent = not (msgs[2] == b'\null')

        if not (isHeader and isFileName and isContent):
            return self._socket.send(Hs.UP, Ms.REQ_ERR)

        fileType = file_type(msgs[2])
        if fileType != self._version:
            return self._socket.send(Hs.UP, Ms.UP_ERR)

        with open(msgs[1].decode(), 'wb+') as file:
            file.write(msgs[2])
        self._socket.send(Hs.UP, Ms.UP_SUC)
        self._state = None


# Установка атрибутов сервера
server_data = Data(PATH)  # Инициализация серверных данных
server_queue = []  # Инициализация пустой очереди для обработчиков

# Установка сокета
server_socket = Socket(AF_INET, SOCK_STREAM)  # Создание socket объекта
server_socket.bind((HOST, PORT))  # Привязка сокета к хосту и порту
server_socket.listen()  # Начать прослушивать соединение

# Обработка и прослушивание входящих соединений
while True:
    # Принятие входящего соединения
    client_socket, client_address = server_socket.accept()

    # Обновление очереди, удаление неактивных обработчиков
    server_queue = [_ for _ in server_queue if _.is_alive()]

    # Обработка соединения
    client_socket.settimeout(60)
    handler = Handler(client_socket, client_address, server_data, server_queue)
    handler.start()
    server_queue.append(handler)
