"""Validação ESTRUTURAL de arquivos .glb (glTF 2.0 binário), sem rede e sem dependências.

Segue a seção "GLB File Format Specification" da especificação glTF 2.0:

    cabeçalho (12 bytes, little-endian): magic 0x46546C67 ("glTF") | version (2) | length (bytes do arquivo)
    chunks em sequência: chunkLength (uint32) | chunkType (uint32) | chunkData (chunkLength bytes)
      - 1º chunk obrigatório: JSON (0x4E4F534A), texto UTF-8 completado com espaços (0x20);
      - 2º chunk opcional: BIN (0x004E4942), no máximo um;
      - outros tipos (extensões) são ignorados, mas precisam caber no arquivo.

O que é verificado: magic, versão 2, `length` igual ao tamanho real e dentro do limite, cada chunk
alinhado a 4 bytes e dentro do arquivo, o último chunk terminando exatamente em `length`, a ordem
JSON -> BIN, e que o JSON é um objeto com asset.version == "2.0".

O que NÃO é verificado (validação semântica): accessors, bufferViews, buffers, malhas, materiais,
texturas, extensões obrigatórias, índices fora do intervalo etc. Um arquivo aprovado aqui é um GLB
bem formado, mas isso NÃO garante que o Three.js (GLTFLoader) consiga renderizá-lo. Para checagem
completa use o glTF-Validator oficial (Khronos) fora do servidor.
"""
import json
import struct

from django.core.exceptions import ValidationError

MAGIC = 0x46546C67  # "glTF"
CHUNK_JSON = 0x4E4F534A  # "JSON"
CHUNK_BIN = 0x004E4942  # "BIN\0"
CABECALHO = 12
CABECALHO_CHUNK = 8
JSON_MAX_BYTES = 2 * 1024 * 1024  # o JSON é lido inteiro na memória: limite para não abusar
INVALIDO = "Arquivo .glb inválido: "


def _erro(mensagem, code):
    return ValidationError(INVALIDO + mensagem, code=code)


def _ler(arquivo, n):
    dados = arquivo.read(n)
    return dados if dados is not None else b""


def validar_glb(arquivo, tamanho_max):
    """Valida a estrutura do GLB em `arquivo` (objeto com read/seek/tell).

    Levanta ValidationError (mensagem em português, `code` começando com "glb_") se algo estiver
    errado. Lê só cabeçalhos e o chunk JSON; os demais chunks são pulados com seek. O arquivo é
    sempre reposicionado no byte 0 ao final, com sucesso ou erro.
    """
    try:
        _validar(arquivo, tamanho_max)
    finally:
        arquivo.seek(0)


def _validar(arquivo, tamanho_max):
    arquivo.seek(0, 2)
    tamanho = arquivo.tell()
    arquivo.seek(0)
    if tamanho > tamanho_max:
        raise _erro(f"o arquivo tem {tamanho} bytes e o limite é {tamanho_max}.", "glb_tamanho")

    cabecalho = _ler(arquivo, CABECALHO)
    if len(cabecalho) < CABECALHO:
        raise _erro("arquivo truncado (cabeçalho incompleto).", "glb_cabecalho_truncado")
    magic, versao, length = struct.unpack("<III", cabecalho)
    if magic != MAGIC:
        raise _erro("não é um glTF binário (glTF 2.0).", "glb_magic")
    if versao != 2:
        raise _erro(f"versão {versao} do GLB não suportada; use glTF 2.0.", "glb_versao")
    if length != tamanho:
        raise _erro(f"o cabeçalho declara {length} bytes, mas o arquivo tem {tamanho} "
                    "(arquivo truncado ou corrompido).", "glb_length")

    posicao = CABECALHO
    indice = 0
    tem_bin = False
    while posicao < length:
        if length - posicao < CABECALHO_CHUNK:
            raise _erro(f"chunk {indice + 1} truncado (cabeçalho do chunk incompleto).", "glb_chunk_truncado")
        tam_chunk, tipo = struct.unpack("<II", _ler(arquivo, CABECALHO_CHUNK))
        posicao += CABECALHO_CHUNK
        if tam_chunk % 4:
            raise _erro(f"chunk {indice + 1} com tamanho {tam_chunk}, que não é múltiplo de 4.",
                        "glb_chunk_alinhamento")
        if tam_chunk > length - posicao:
            raise _erro(f"chunk {indice + 1} ultrapassa o fim do arquivo.", "glb_chunk_excede")

        if indice == 0:
            if tipo != CHUNK_JSON:
                raise _erro("o primeiro chunk precisa ser o JSON.", "glb_sem_json")
            _validar_json(arquivo, tam_chunk)
        elif tipo == CHUNK_JSON:
            raise _erro("mais de um chunk JSON.", "glb_json_duplicado")
        elif tipo == CHUNK_BIN:
            if tem_bin:
                raise _erro("mais de um chunk BIN.", "glb_bin_duplicado")
            if indice != 1:
                raise _erro("o chunk BIN só pode vir logo depois do JSON.", "glb_bin_posicao")
            tem_bin = True
            arquivo.seek(tam_chunk, 1)
        else:  # tipo desconhecido: a especificação manda ignorar
            arquivo.seek(tam_chunk, 1)
        posicao += tam_chunk
        indice += 1

    if indice == 0:
        raise _erro("o arquivo não tem o chunk JSON.", "glb_sem_json")


def _validar_json(arquivo, tam_chunk):
    if tam_chunk > JSON_MAX_BYTES:
        raise _erro(f"o JSON do modelo passa de {JSON_MAX_BYTES // (1024 * 1024)} MB.", "glb_json_grande")
    bruto = _ler(arquivo, tam_chunk)
    if len(bruto) != tam_chunk:
        raise _erro("chunk JSON truncado.", "glb_chunk_truncado")
    bruto = bruto.rstrip(b" ")  # padding de espaços (0x20) previsto na especificação
    if not bruto.strip():
        raise _erro("o chunk JSON está vazio.", "glb_json_vazio")
    try:
        dados = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise _erro("o chunk JSON não é um JSON UTF-8 válido.", "glb_json_invalido") from None
    if not isinstance(dados, dict):
        raise _erro("o chunk JSON precisa ser um objeto.", "glb_json_invalido")
    asset = dados.get("asset")
    if not isinstance(asset, dict) or "version" not in asset:
        raise _erro('o JSON não tem "asset.version" (obrigatório no glTF).', "glb_asset")
    if asset["version"] != "2.0":
        raise _erro(f'asset.version é {asset["version"]!r}; só glTF "2.0" é aceito.', "glb_asset_versao")
