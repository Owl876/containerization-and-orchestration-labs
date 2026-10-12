#!/usr/bin/env bash
set -euo pipefail

echo ">>> 1) секрет с токеном бота для встроенного Alertmanager-receiver"
echo "    (впиши сюда свой настоящий токен вместо плейсхолдера и запусти руками):"
cat <<'CMD'
kubectl create secret generic telegram-bot-token -n monitoring \
  --from-literal=token='<ТВОЙ_ТОКЕН>'
CMD

echo ""
echo ">>> 2) секрет для сервиса-моста (токен + chat_id + file_id стикера)"
cat <<'CMD'
kubectl create secret generic telegram-bridge-secrets -n monitoring \
  --from-literal=bot-token='<ТВОЙ_ТОКЕН>' \
  --from-literal=chat-id='1001306095' \
  --from-literal=sticker-file-id='CAACAgQAAxkBAAMDasy8iptqbWqsXjUxlPIF9qhn1WIAAnEMAAJ6RqBQE3ia2E3EaVw9BA'
CMD

echo ""
echo "Команды выше просто выведены на экран — выполни их сама (с реальным токеном)."
echo "Дальше жми Enter, чтобы продолжить сборкой и деплоем."
read -r

echo ">>> 3) собираем образ моста внутри minikube"
cd telegram-bridge
minikube image build -t telegram-bridge:local .
cd ..

echo ">>> 4) ставим сам мост в namespace monitoring"
helm install telegram-bridge charts/telegram-bridge -n monitoring

echo ">>> 5) накатываем обновлённый Alertmanager (секрет-файл токена + routing)"
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring \
  -f observability/kube-prometheus-stack-values.yaml

echo ">>> готово, жди пока поды monitoring перекатятся"
kubectl get pods -n monitoring -w
