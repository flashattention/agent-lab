---
title: "FAISS"
description: "Meta의 벡터 유사도 검색 라이브러리 FAISS: 인덱스 종류와 LangChain 사용 시 주의점"
order: 13
source: "https://faiss.ai/"
tags: [vector-db, faiss, library, ann]
---

# FAISS

FAISS(Facebook AI Similarity Search)는 Meta가 만든 **벡터 검색 라이브러리**입니다. 서버나 DB가 아니라 프로세스 안에서 인덱스 객체를 만들고 검색합니다. Flat, IVF, PQ, HNSW 등 거의 모든 ANN 기법의 레퍼런스 구현이 있어 오프라인 배치 처리, 연구, 인덱스 실험에 많이 쓰입니다.

> [!IMPORTANT]
> LangChain의 FAISS 래퍼(`FAISS` 클래스)는 **`langchain_community.vectorstores`** 에 있습니다. AgentLab은 `langchain_community`를 금지 목록에 두고 있으므로 강의·예제에서는 쓰지 않습니다. 인메모리 검색이 필요하면 [InMemoryVectorStore](/docs/vector-db/03-in-memory)나 [Qdrant `:memory:`](/docs/vector-db/04-qdrant)를 쓰세요.

> [!NOTE]
> `faiss-cpu`는 AgentLab 샌드박스에 **설치되어 있지 않습니다.** 아래 코드는 참고용이며 API는 [FAISS 위키](https://github.com/facebookresearch/faiss/wiki)를 확인하세요.

## Import

```bash
pip install faiss-cpu   # GPU: faiss-gpu 계열 (CUDA 버전에 맞춰 설치)
```

```python
import faiss
import numpy as np
```

## 시그니처 (주요 인덱스)

```python
faiss.IndexFlatL2(d)                              # 정확 검색, L2
faiss.IndexFlatIP(d)                              # 정확 검색, 내적 (정규화하면 코사인)
faiss.IndexHNSWFlat(d, M)                         # HNSW 그래프
faiss.IndexIVFFlat(quantizer, d, nlist)           # IVF, train 필요
faiss.IndexIVFPQ(quantizer, d, nlist, m, nbits)   # IVF + PQ 압축
faiss.index_factory(d, "IVF256,PQ16")             # 문자열로 조합
faiss.normalize_L2(x)                             # in-place L2 정규화
```

## 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `d` | `int` | (필수) | 벡터 차원 |
| `M` | `int` | (필수) | HNSW 노드당 이웃 수 |
| `nlist` | `int` | (필수) | IVF 클러스터(셀) 수 |
| `m` | `int` | (필수) | PQ 부분 공간 수 (`d`의 약수) |
| `nbits` | `int` | (필수) | 부분 코드당 비트 수 (보통 8) |
| `index.nprobe` | `int` | `1` | IVF 검색 시 탐색할 셀 수 (속성) |

## 메서드와 반환값

| 메서드 | 반환 | 설명 |
|---|---|---|
| `index.train(x)` | `None` | IVF/PQ 계열은 추가 전에 학습 필요 (`index.is_trained`) |
| `index.add(x)` | `None` | `float32` 2차원 배열 `(n, d)` 추가. ID는 0부터 순번 |
| `index.add_with_ids(x, ids)` | `None` | 사용자 ID 지정 (`IndexIDMap`으로 감싸야 하는 인덱스가 있음) |
| `index.search(q, k)` | `(D, I)` | 거리 배열과 ID 배열, 각 `(nq, k)`. 결과 없음은 `-1` |
| `faiss.write_index(index, path)` / `faiss.read_index(path)` | | 파일 저장·로드 |

## 예제

```python
import faiss
import numpy as np

d = 1536
xb = np.random.rand(10_000, d).astype("float32")
xq = np.random.rand(3, d).astype("float32")

# 코사인 유사도 = 정규화 + 내적
faiss.normalize_L2(xb)
faiss.normalize_L2(xq)

index = faiss.IndexHNSWFlat(d, 32, faiss.METRIC_INNER_PRODUCT)
index.add(xb)
scores, ids = index.search(xq, 5)
print(ids[0], scores[0])
```

IVF는 학습이 필요합니다.

```python
quantizer = faiss.IndexFlatL2(d)
ivf = faiss.IndexIVFFlat(quantizer, d, 100)
ivf.train(xb)       # 대표 샘플로 k-means 학습
ivf.add(xb)
ivf.nprobe = 10     # 정확도↑ 속도↓
D, I = ivf.search(xq, 5)
```

## 주의사항

> [!WARNING]
> FAISS는 **메타데이터·문서 본문을 저장하지 않습니다.** 정수 ID ↔ 문서 매핑과 필터링은 직접 구현해야 합니다. 메타데이터 필터가 필요한 서비스라면 벡터 DB를 쓰는 편이 낫습니다.

> [!WARNING]
> 입력은 반드시 C-연속 `float32` 배열이어야 합니다. `float64` numpy 배열을 넣으면 오류가 납니다.

> [!TIP]
> 동시 쓰기, 영속성, 복제가 필요해지는 순간이 벡터 DB로 옮길 때입니다. FAISS로 찾은 인덱스 설정(HNSW M, IVF nlist 등)은 Qdrant·Milvus 튜닝의 출발점으로 쓸 수 있습니다.

## 관련 문서

- [벡터 검색 핵심 개념 — 인덱스 유형](/docs/vector-db/01-concepts)
- [InMemoryVectorStore](/docs/vector-db/03-in-memory)
- [벡터 DB 비교](/docs/vector-db/02-comparison)
- [FAISS 공식 문서](https://faiss.ai/)
- [FAISS 인덱스 선택 가이드](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index)
