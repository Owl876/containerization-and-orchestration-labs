package main

import (
	"crypto/sha256"
	"fmt"
	"log"
	"net/http"
	"os"
	"runtime"
	"strconv"
	"sync"
)

const mib = 1024 * 1024

func main() {
	runtime.GOMAXPROCS(1)

	var memoryMu sync.Mutex
	var heldMemory [][]byte
	var burnOnce sync.Once

	mux := http.NewServeMux()

	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, "ok")
	})

	mux.HandleFunc("GET /eat", func(w http.ResponseWriter, r *http.Request) {
		mb, err := strconv.Atoi(r.URL.Query().Get("mb"))
		if err != nil || mb <= 0 || mb > int(^uint(0)>>1)/mib {
			http.Error(w, "mb must be a positive integer within the addressable range", http.StatusBadRequest)
			return
		}

		block := make([]byte, mb*mib)
		for i := range block {
			block[i] = 1
		}
		memoryMu.Lock()
		heldMemory = append(heldMemory, block)
		memoryMu.Unlock()
		fmt.Fprintf(w, "holding %d MiB more until process exit\n", mb)
	})

	mux.HandleFunc("GET /burn", func(w http.ResponseWriter, r *http.Request) {
		burnOnce.Do(func() {
			go func() {
				var data [32]byte
				for {
					data = sha256.Sum256(data[:])
				}
			}()
		})
		fmt.Fprintln(w, "one CPU worker running until process exit")
	})

	addr := os.Getenv("API_ADDR")
	if addr == "" {
		addr = ":8080"
	}

	log.Printf("PandaRecovery lab API: pid=%d address=%s", os.Getpid(), addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}
