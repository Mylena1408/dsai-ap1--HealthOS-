from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
import jwt
from config.settings import settings

class JWTHandler:
    """
    Classe responsável pela geração e validação de tokens JWT.
    Trata a segurança de autenticação stateless da aplicação.
    """

    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Gera um token de acesso com tempo de vida curto.
        """
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=self.access_token_expire_minutes))
        to_encode.update({"exp": expire, "type": "access"})

        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """
        Gera um token de atualização com tempo de vida longo.
        """
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})

        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decodifica e valida a assinatura do token.
        Lança jwt.PyJWTError se o token for inválido ou expirado.
        """
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

    def get_token_payload(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Tenta decodificar o token, retornando None em caso de falha.
        """
        try:
            return self.decode_token(token)
        except (jwt.PyJWTError, Exception):
            return None
