{{- define "shop.podSpread" -}}
{{- if eq .root.Values.podSpread.mechanism "antiAffinity" }}
affinity:
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app: {{ .component }}
        topologyKey: kubernetes.io/hostname
{{- else }}
topologySpreadConstraints:
  - maxSkew: {{ .root.Values.podSpread.maxSkew }}
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: {{ .root.Values.podSpread.whenUnsatisfiable }}
    labelSelector:
      matchLabels:
        app: {{ .component }}
{{- end }}
{{- end }}
