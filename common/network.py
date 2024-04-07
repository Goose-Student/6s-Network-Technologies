from typing import Tuple

# socket imports
from socket import socket
from _socket import getdefaulttimeout


class Headers:
    """
    Класс, содержащий константы заголовков.

    Attributes:
        CONN: Константа для подключения.
        AUTH: Константа для аутентификации.
        REG: Константа для регистрации.
        UP: константа для загрузки.
    """
    CONN = b'connect'
    AUTH = b'auth'
    REG = b'reg'
    UP = b'upload'


class Messages:
    """
    Класс, содержащий сообщения для обмена данными.

    Attributes:
        CONN_SUC: Успешное подключение.
        CONN_ERR: Ошибка подключения.
        AUTH_SUC: Успешная аутентификация.
        AUTH_ERR: Неверный логин или пароль.
        REG_SUC: Успешная регистрация.
        REG_ERR: Пользователь уже существует.
        UP_SUC: Успешная передача файла.
        UP_ERR: Неверный тип файла.
        REQ_ERR: Неверный запрос.
    """
    # Сообщения о подключении
    CONN_SUC = 'успешное подключение'.encode()
    CONN_ERR = 'ошибка подключения'.encode()

    # Сообщения авторизации
    AUTH_SUC = 'успешная аутентификация'.encode()
    AUTH_ERR = 'неверный логин или пароль'.encode()

    # Регистрационные сообщения
    REG_SUC = 'успешная регистрация'.encode()
    REG_ERR = 'пользователь уже существует'.encode()

    # Файловые сообщения
    UP_SUC = 'успешная передача файла'.encode()
    UP_ERR = 'неверный тип файла'.encode()

    # Общие сообщения
    REQ_ERR = 'неверный запрос'.encode()


class Socket(socket):
    def __init__(self, *args, **kwargs):
        """Расширение класса socket с дополнительной функциональностью."""
        super().__init__(*args, **kwargs)
        self._separator = b'@sep'
        self._end = b'@end'
        self._chunk_size = 1024

    # Attribute methods
    @property
    def separator(self) -> bytes:
        return self._separator

    @separator.setter
    def separator(self, value: bytes) -> None:
        self._separator = value

    @property
    def end(self) -> bytes:
        return self._end

    @end.setter
    def end(self, value: bytes):
        self._end = value

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @chunk_size.setter
    def chunk_size(self, value: int):
        self._chunk_size = value

    # Socket methods
    def receive(self, target_len: int = 3) -> Tuple[bytes, ...]:
        """
        Получение сообщения до тех пор, пока не будет найден конечный маркер.

        Args:
            target_len (int): Целевая длина для получения. Значение по умолчанию равно 3.

        Returns:
            Tuple[bytes, ...]: Кортеж полученных сообщений.
        """
        buffer = b''
        while not (self.end in buffer):
            chunk = super().recv(self.chunk_size)
            if not chunk:
                break
            buffer += chunk

        buffer = buffer.replace(self.end, b'')
        buffer = buffer.split(self.separator)[:target_len]
        buffer += [b'@null'] * (target_len - len(buffer))
        return tuple(buffer)

    def send(self, *msgs: bytes) -> None:
        """
        Отправка сообщения, соединенные разделителем.

       Args:
           *msgs (bytes): сообщения для отправки.
       """
        buffer = self.separator.join(msgs)

        while buffer:
            chunk = buffer[:self.chunk_size]
            buffer = buffer[self.chunk_size:]
            super().sendall(chunk)
        super().sendall(self.end)

    def accept(self) -> Tuple['Socket', Tuple]:
        """
        Принимает входящее соединение и возвращает новый объект сокета и адрес.

        Returns:
            Tuple['Socket', Tuple]: Tuple, содержащий новый объект сокета и адрес.
        """
        fd, addr = self._accept()
        sock = Socket(self.family, self.type, self.proto, fileno=fd)
        if getdefaulttimeout() is None and self.gettimeout():
            sock.setblocking(True)
        return sock, addr
