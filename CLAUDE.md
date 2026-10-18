# Regras operacionais dos agentes

Complementam o `AGENTS.md`, sem alterá-lo. Aprovadas pelo responsável pelo projeto em 2026-10-18, depois da perda de pareceres do revisor causada por `git checkout -q docs`.

## 1. Entregar com os próprios documentos commitados

Antes de devolver o trabalho ao próximo agente, cada agente commita os documentos que escreveu ou alterou: especificações, critérios, pareceres e registros. O próximo agente deve encontrar a árvore de trabalho limpa, sem alteração de outro agente pendente de commit.

## 2. Descartar só o que é seu, arquivo por arquivo

Antes de qualquer comando que descarta alterações locais, rode `git status` e confira de quem é cada alteração. Isso vale para `git checkout -- <caminho>`, `git restore`, `git stash`, `git reset --hard`, `git clean` e equivalentes.

- Descarte apenas arquivos que você mesmo alterou, nomeados um a um. Nunca descarte por pasta, por padrão de nome nem pela árvore inteira.
- Para desfazer uma reformatação ou uma edição sua, use o caminho reverso específico, como uma edição pontual ou o descarte do arquivo nomeado. Nunca use um descarte amplo.
- Se houver alteração de outro agente no caminho, não a toque. Registre a dúvida e peça orientação.
