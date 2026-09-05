// the Go baseline: the same three routes on net/http with the standard
// library router.
//
// it does the same work the Laurel program does: route, decode a typed path
// parameter, parse a urlencoded form, set the same five security headers, and
// write a small JSON body.
package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
)

const (
	csp             = "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
	referrerPolicy  = "strict-origin-when-cross-origin"
	permissionsPol  = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
	frameOptions    = "DENY"
	contentTypeOpts = "nosniff"
)

// the same headers Laurel's security policy applies, set by hand
func secure(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("content-security-policy", csp)
		h.Set("referrer-policy", referrerPolicy)
		h.Set("permissions-policy", permissionsPol)
		h.Set("x-frame-options", frameOptions)
		h.Set("x-content-type-options", contentTypeOpts)
		next.ServeHTTP(w, r)
	})
}

func writeJSON(w http.ResponseWriter, code int, body string) {
	w.Header().Set("content-type", "application/json; charset=utf-8")
	w.Header().Set("content-length", strconv.Itoa(len(body)))
	w.WriteHeader(code)
	_, _ = w.Write([]byte(body))
}

func handleJSON(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, `{"message":"hello"}`)
}

func handleEcho(w http.ResponseWriter, r *http.Request) {
	id, err := strconv.ParseUint(r.PathValue("id"), 10, 64)
	if err != nil {
		http.Error(w, "invalid route parameter", http.StatusBadRequest)
		return
	}
	writeJSON(w, http.StatusOK, fmt.Sprintf(`{"id":%d}`, id))
}

func handleSubmit(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "malformed form", http.StatusBadRequest)
		return
	}
	name := r.PostFormValue("name")
	if name == "" {
		http.Error(w, "name is required", http.StatusBadRequest)
		return
	}
	writeJSON(w, http.StatusOK, `{"name":"`+escapeJSON(name)+`"}`)
}

// the Laurel program escapes with render.escape_json; this is the same job
func escapeJSON(s string) string {
	out := make([]byte, 0, len(s)+8)
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch c {
		case '"':
			out = append(out, '\\', '"')
		case '\\':
			out = append(out, '\\', '\\')
		case '\n':
			out = append(out, '\\', 'n')
		case '\r':
			out = append(out, '\\', 'r')
		case '\t':
			out = append(out, '\\', 't')
		default:
			if c < 0x20 {
				out = append(out, fmt.Sprintf(`\u%04x`, c)...)
			} else {
				out = append(out, c)
			}
		}
	}
	return string(out)
}

func main() {
	addr := os.Getenv("BENCH_ADDR")
	if addr == "" {
		addr = "127.0.0.1:8082"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /json", handleJSON)
	mux.HandleFunc("GET /echo/{id}", handleEcho)
	mux.HandleFunc("POST /submit", handleSubmit)

	server := &http.Server{Addr: addr, Handler: secure(mux)}
	log.Printf("go-bench: listening on %s", addr)
	if err := server.ListenAndServe(); err != nil {
		log.Fatalf("go-bench: %v", err)
	}
}
