# Comandos do Projeto (CI/CD, qualidade e release)

Este guia resume os comandos usados para deixar o projeto passando em lint/type-check/testes e publicar release com tag.

## 1) Preparar ambiente local

```bash
cd /home/jezuis/Desktop/std/libs/python/noaawc
pipenv install
pipenv shell
```

Opcional (sem entrar no shell):

```bash
pipenv run <comando>
```

## 2) Qualidade de código

### 2.1 Ruff (lint)

```bash
pipenv run ruff check .
```

### 2.2 Ruff (formatação)

Aplicar formatação:

```bash
pipenv run ruff format noaawc/main.py noaawc/variables.py setup.py test_plot.py teste_keys.py tests/test_animator_api.py tests/test_metadata.py
```

Checar se está tudo formatado:

```bash
pipenv run ruff format --check .
```

Observação: se existir `Untitled.ipynb` local e não versionado, ele pode aparecer no `format --check .`. No CI isso normalmente não impacta se não estiver no Git.

## 3) Type-check (mypy)

Mesmo comando usado no workflow:

```bash
pipenv run mypy noaawc/ --ignore-missing-imports
```

## 4) Testes

### 4.1 Suite principal

```bash
pipenv run pytest tests/ -v
```

### 4.2 Metadados/versionamento

```bash
pipenv run pytest tests/test_metadata.py -q
```

## 5) Build de distribuição

```bash
pipenv run python -m pip install -U build twine
pipenv run python -m build
pipenv run twine check dist/*
```

## 6) Rodar etapas do workflow localmente (manual)

Como o `act` não está instalado, use a sequência abaixo para reproduzir o pipeline:

```bash
# Lint + format + mypy
pipenv run ruff check . --output-format=github
pipenv run ruff format --check .
pipenv run mypy noaawc/ --ignore-missing-imports

# Testes unitários (sem integração)
pipenv run pytest tests/ -v -m "not integration" --tb=short

# Build
pipenv run python -m build
pipenv run twine check dist/*
```

## 7) Git: checagem de estado

```bash
git status --short
git status -sb
git diff --cached --name-only
```

Listar rastreados ausentes localmente:

```bash
missing=0
while IFS= read -r f; do
  if [[ ! -e "$f" ]]; then
    echo "$f"
    missing=1
  fi
done < <(git ls-files)
[[ $missing -eq 0 ]] && echo "(nenhum)"
```

Listar locais não rastreados:

```bash
git ls-files --others --exclude-standard
```

## 8) Commit limpo (somente arquivos desejados)

Exemplo (arquivos de código):

```bash
git add noaawc/main.py noaawc/variables.py setup.py tests/test_metadata.py
git commit -m "fix: address mypy typing issues"
git push origin main
```

## 9) Commit de remoções (arquivos legados)

```bash
git ls-files --deleted -z | xargs -0 -r git rm --
git commit -m "chore: remove legacy tracked artifacts"
git push origin main
```

## 10) Release com tag

### 10.1 Atualizar versão e changelog

- Atualize `setup.py` (campo `version`).
- Atualize `CHANGELOG.md` com a seção da nova versão.

### 10.2 Criar commit + tag + push

```bash
git add setup.py CHANGELOG.md .github/workflows/ci-publish.yml tests/test_metadata.py
git commit -m "release: v0.3.1"
git tag -f v0.3.1
git push origin main
git push origin v0.3.1
```

## 11) Comandos rápidos de validação final

```bash
pipenv run ruff check .
pipenv run ruff format --check .
pipenv run mypy noaawc/ --ignore-missing-imports
pipenv run pytest tests/ -v
```

Se todos passarem, o projeto está pronto para CI/CD.
