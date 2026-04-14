import chromadb

from flowstate.config import settings


def get_chroma():
	return chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
