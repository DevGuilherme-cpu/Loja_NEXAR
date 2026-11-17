"""Validação estrutural de GLB (loja/glb.py). Rodar com: python manage.py test loja.test_glb

Os fixtures são gerados em código (sem arquivos binários no repositório). Os modelos reais
static/modelos/*.glb são só lidos.
"""
import json
import struct
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from .glb import CHUNK_BIN, CHUNK_JSON, JSON_MAX_BYTES, validar_glb

LIMITE = 15 * 1024 * 1024


def chunk(tipo, dados, pad=b"\x00"):
    """chunkLength + chunkType + dados completados até múltiplo de 4."""
    dados += pad * (-len(dados) % 4)
    return struct.pack("<II", len(dados), tipo) + dados


def chunk_json(obj=None, bruto=None):
    dados = bruto if bruto is not None else json.dumps(obj if obj is not None else {"asset": {"version": "2.0"}}).encode()
    return chunk(CHUNK_JSON, dados, pad=b" ")


def montar(*chunks, versao=2, magic=b"glTF", length=None):
    corpo = b"".join(chunks)
    total = 12 + len(corpo) if length is None else length
    return magic + struct.pack("<II", versao, total) + corpo


# GLB mínimo válido: só o chunk JSON {"asset":{"version":"2.0"}} com padding de espaços
GLB_MINIMO = montar(chunk_json())
# GLB válido com chunk BIN (buffer de 5 bytes completado com zeros)
GLB_COM_BIN = montar(chunk_json({"asset": {"version": "2.0"}, "buffers": [{"byteLength": 5}]}),
                     chunk(CHUNK_BIN, b"\x01\x02\x03\x04\x05"))


class ValidarGlbTest(SimpleTestCase):
    def validar(self, conteudo, limite=LIMITE):
        validar_glb(BytesIO(conteudo), limite)

    def assertInvalido(self, conteudo, code, limite=LIMITE):
        arquivo = BytesIO(conteudo)
        arquivo.seek(5)  # posição qualquer: o validador precisa começar do 0 e voltar para o 0
        with self.assertRaises(ValidationError) as ctx:
            validar_glb(arquivo, limite)
        self.assertEqual(ctx.exception.code, code, ctx.exception.messages)
        self.assertTrue(ctx.exception.messages[0].startswith("Arquivo .glb inválido"))
        self.assertEqual(arquivo.tell(), 0)

    # ---- válidos ----
    def test_fixtures_validos(self):
        self.assertEqual(len(GLB_MINIMO) % 4, 0)
        self.validar(GLB_MINIMO)
        self.validar(GLB_COM_BIN)

    def test_chunk_desconhecido_e_ignorado(self):
        self.validar(montar(chunk_json(), chunk(CHUNK_BIN, b"abcd"), chunk(0x12345678, b"extensao")))
        self.validar(montar(chunk_json(), chunk(0x12345678, b"x")))

    def test_modelos_reais_do_projeto(self):
        for nome in ("oculos.glb", "tenis.glb"):
            with self.subTest(nome), open(Path(settings.BASE_DIR) / "static" / "modelos" / nome, "rb") as f:
                validar_glb(f, LIMITE)
                self.assertEqual(f.tell(), 0)

    def test_reposiciona_em_zero_com_sucesso(self):
        for arquivo in (BytesIO(GLB_COM_BIN), SimpleUploadedFile("p.glb", GLB_COM_BIN)):
            with self.subTest(type(arquivo).__name__):
                arquivo.seek(7)
                validar_glb(arquivo, LIMITE)
                self.assertEqual(arquivo.tell(), 0)
                self.assertEqual(arquivo.read(), GLB_COM_BIN)

    # ---- cabeçalho ----
    def test_magic_errado(self):
        self.assertInvalido(montar(chunk_json(), magic=b"glTX"), "glb_magic")

    def test_versao_1(self):
        self.assertInvalido(montar(chunk_json(), versao=1), "glb_versao")

    def test_length_maior_e_menor_que_o_arquivo(self):
        self.assertInvalido(montar(chunk_json(), length=len(GLB_MINIMO) + 4), "glb_length")
        self.assertInvalido(montar(chunk_json(), length=len(GLB_MINIMO) - 4), "glb_length")

    def test_truncado_no_meio_do_cabecalho(self):
        self.assertInvalido(GLB_MINIMO[:7], "glb_cabecalho_truncado")
        self.assertInvalido(b"", "glb_cabecalho_truncado")

    def test_maior_que_o_limite(self):
        self.assertInvalido(GLB_MINIMO, "glb_tamanho", limite=len(GLB_MINIMO) - 1)

    def test_sem_nenhum_chunk(self):
        self.assertInvalido(montar(), "glb_sem_json")

    # ---- chunks ----
    def test_truncado_no_meio_do_chunk(self):
        # cortado dentro dos dados do BIN (length do cabeçalho original): não bate com o tamanho real
        self.assertInvalido(GLB_COM_BIN[:-3], "glb_length")
        # cortado dentro do cabeçalho do 2º chunk, com length corrigido para o tamanho cortado
        cortado = montar(chunk_json(), chunk(CHUNK_BIN, b"abcd")[:4])
        self.assertInvalido(cortado, "glb_chunk_truncado")

    def test_chunk_ultrapassa_o_fim(self):
        dados = b"abcd"
        falso = struct.pack("<II", 64, CHUNK_BIN) + dados  # declara 64 bytes, só existem 4
        self.assertInvalido(montar(chunk_json(), falso), "glb_chunk_excede")

    def test_chunk_length_nao_multiplo_de_4(self):
        bruto = b'{"asset":{"version":"2.0"}} '  # 28 bytes
        sem_padding = struct.pack("<II", len(bruto) + 1, CHUNK_JSON) + bruto + b" "  # 29 bytes
        self.assertInvalido(montar(sem_padding), "glb_chunk_alinhamento")

    def test_primeiro_chunk_bin(self):
        self.assertInvalido(montar(chunk(CHUNK_BIN, b"abcd"), chunk_json()), "glb_sem_json")

    def test_dois_chunks_bin(self):
        self.assertInvalido(montar(chunk_json(), chunk(CHUNK_BIN, b"abcd"), chunk(CHUNK_BIN, b"efgh")),
                            "glb_bin_duplicado")

    def test_bin_fora_da_segunda_posicao(self):
        self.assertInvalido(montar(chunk_json(), chunk(0x12345678, b"x"), chunk(CHUNK_BIN, b"abcd")),
                            "glb_bin_posicao")

    def test_dois_chunks_json(self):
        self.assertInvalido(montar(chunk_json(), chunk_json()), "glb_json_duplicado")

    # ---- conteúdo do JSON ----
    def test_json_vazio(self):
        self.assertInvalido(montar(chunk(CHUNK_JSON, b"")), "glb_json_vazio")
        self.assertInvalido(montar(chunk(CHUNK_JSON, b"    ")), "glb_json_vazio")

    def test_json_invalido(self):
        self.assertInvalido(montar(chunk_json(bruto=b'{"asset": ')), "glb_json_invalido")
        self.assertInvalido(montar(chunk_json(bruto=b"\xff\xfe{}")), "glb_json_invalido")
        self.assertInvalido(montar(chunk_json(bruto=b"[1, 2]")), "glb_json_invalido")

    def test_json_sem_asset(self):
        self.assertInvalido(montar(chunk_json({"scenes": []})), "glb_asset")
        self.assertInvalido(montar(chunk_json({"asset": {}})), "glb_asset")
        self.assertInvalido(montar(chunk_json({"asset": "2.0"})), "glb_asset")

    def test_asset_version_errada(self):
        self.assertInvalido(montar(chunk_json({"asset": {"version": "1.0"}})), "glb_asset_versao")
        self.assertInvalido(montar(chunk_json({"asset": {"version": 2.0}})), "glb_asset_versao")

    def test_json_grande_demais(self):
        bruto = b'{"asset":{"version":"2.0"}}' + b" " * JSON_MAX_BYTES
        self.assertInvalido(montar(chunk_json(bruto=bruto)), "glb_json_grande")
