mod store;
use axum::{
    extract::{DefaultBodyLimit, State},
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use rusqlite::Connection;
use serde_json::{json, Value};
use std::{
    env,
    sync::{Arc, Mutex, OnceLock},
};
use subtle::ConstantTimeEq;

#[derive(Clone)]
struct App {
    db: Arc<Mutex<Connection>>,
    token: Arc<String>,
}
fn schema(properties: Value, required: &[&str]) -> Value {
    json!({"type":"object","properties":properties,"required":required,"additionalProperties":false})
}
fn tools() -> &'static Value {
    static TOOLS: OnceLock<Value> = OnceLock::new();
    TOOLS.get_or_init(|| json!([
 {"name":"criar_item","description":"Cria grupo, pasta ou atividade. Uma pasta pode ficar em grupo ou pasta; atividade pode ficar em pasta ou atividade. Prazo opcional no formato DD/MM/AAAA.","inputSchema":schema(json!({"tipo":{"type":"string","enum":["grupo","pasta","atividade"]},"titulo":{"type":"string"},"pai_id":{"type":["integer","null"]},"descricao":{"type":["string","null"],"description":"Texto em Markdown, organizado como README. Ao escrever ou editar, use títulos, listas e blocos de código quando úteis; preserve informação e formatação existentes, sem inventar conteúdo."},"prazo":{"type":["string","null"],"description":"DD/MM/AAAA"},"lembrete_utc":{"type":["string","null"],"description":"Data e hora ISO 8601 com fuso; armazenado em UTC"},"tags":{"type":["array","null"],"items":{"type":"string"},"description":"Etiquetas da atividade; lista completa, até 12, cada nome com até 32 caracteres."}}), &["tipo","titulo"])},
 {"name":"listar_itens","description":"Lista itens em páginas resumidas. Use proximo_cursor na próxima consulta; detalhes=true inclui descrição e datas de registro.","annotations":{"readOnlyHint":true,"destructiveHint":false,"openWorldHint":false},"inputSchema":schema(json!({"pai_id":{"type":"integer"},"tipo":{"type":"string","enum":["grupo","pasta","atividade"]},"concluida":{"type":"boolean"},"busca":{"type":"string"},"limite":{"type":"integer","minimum":1,"maximum":500},"cursor":{"type":"integer","minimum":0},"detalhes":{"type":"boolean"}}), &[])},
 {"name":"obter_item","description":"Obtém detalhes e uma página resumida de filhos diretos. Descrições podem conter Markdown; mantenha a estrutura ao editá-las. Continue com listar_itens e proximo_cursor.","annotations":{"readOnlyHint":true,"destructiveHint":false,"openWorldHint":false},"inputSchema":schema(json!({"id":{"type":"integer"},"limite":{"type":"integer","minimum":1,"maximum":500},"cursor":{"type":"integer","minimum":0}}), &["id"])},
 {"name":"atualizar_item","description":"Altera título, descrição, prazo, conclusão ou pai. Use null para remover prazo, descrição ou pai. Não permite ciclos.","inputSchema":schema(json!({"id":{"type":"integer"},"titulo":{"type":"string"},"descricao":{"type":["string","null"],"description":"Texto em Markdown, organizado como README. Ao escrever ou editar, use títulos, listas e blocos de código quando úteis; preserve informação e formatação existentes, sem inventar conteúdo."},"prazo":{"type":["string","null"],"description":"DD/MM/AAAA"},"lembrete_utc":{"type":["string","null"],"description":"Data e hora ISO 8601 com fuso; armazenado em UTC"},"tags":{"type":["array","null"],"items":{"type":"string"},"description":"Etiquetas da atividade; lista completa, até 12, cada nome com até 32 caracteres."},"concluida":{"type":"boolean"},"pai_id":{"type":["integer","null"]}}), &["id"])},
 {"name":"excluir_item","annotations":{"readOnlyHint":false,"destructiveHint":true,"openWorldHint":false},"description":"Exclui item e TODOS os seus descendentes permanentemente. Exige confirmar=true.","inputSchema":schema(json!({"id":{"type":"integer"},"confirmar":{"type":"boolean"}}), &["id","confirmar"])}
]))
}
async fn health() -> &'static str {
    "ok"
}
async fn mcp(State(app): State<App>, headers: HeaderMap, Json(req): Json<Value>) -> Response {
    let expected = format!("Bearer {}", app.token);
    let actual = headers
        .get("authorization")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    if expected.as_bytes().ct_eq(actual.as_bytes()).unwrap_u8() != 1 {
        return (StatusCode::UNAUTHORIZED, "Unauthorized").into_response();
    }
    if let Some(origin) = headers.get("origin") {
        if !origin.as_bytes().is_empty() {
            return (StatusCode::FORBIDDEN, "Browser origins are not supported").into_response();
        }
    }
    let Some(id) = req.get("id") else {
        return StatusCode::ACCEPTED.into_response();
    };
    let method = req.get("method").and_then(Value::as_str).unwrap_or("");
    let response = match method {
        "initialize" => {
            let requested = req
                .pointer("/params/protocolVersion")
                .and_then(Value::as_str)
                .unwrap_or("2025-03-26");
            let version = if ["2025-03-26", "2025-06-18", "2025-11-25"].contains(&requested) {
                requested
            } else {
                "2025-06-18"
            };
            json!({"jsonrpc":"2.0","id":id,"result":{"protocolVersion":version,"capabilities":{"tools":{}},"serverInfo":{"name":"personal-todo","version":"0.2.0"}}})
        }
        "ping" => json!({"jsonrpc":"2.0","id":id,"result":{}}),
        "tools/list" => json!({"jsonrpc":"2.0","id":id,"result":{"tools":tools()}}),
        "tools/call" => {
            let name = req
                .pointer("/params/name")
                .and_then(Value::as_str)
                .unwrap_or("");
            let args = req
                .pointer("/params/arguments")
                .cloned()
                .unwrap_or(json!({}));
            let result = app
                .db
                .lock()
                .map_err(|_| "Banco indisponível".to_string())
                .and_then(|mut db| store::call(&mut db, name, &args));
            match result {
                Ok(v) => {
                    json!({"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text":v.to_string()}]}})
                }
                Err(e) => {
                    json!({"jsonrpc":"2.0","id":id,"result":{"isError":true,"content":[{"type":"text","text":e}]}})
                }
            }
        }
        _ => json!({"jsonrpc":"2.0","id":id,"error":{"code":-32601,"message":"Method not found"}}),
    };
    Json(response).into_response()
}
#[tokio::main]
async fn main() {
    let token = env::var("MCP_TOKEN").expect("MCP_TOKEN obrigatório");
    assert!(
        token.len() >= 32,
        "MCP_TOKEN deve ter no mínimo 32 caracteres"
    );
    let path = env::var("DATABASE_PATH").unwrap_or_else(|_| "todo.sqlite3".into());
    let db = Connection::open(path).expect("falha ao abrir banco");
    store::init(&db).expect("falha ao iniciar banco");
    let state = App {
        db: Arc::new(Mutex::new(db)),
        token: Arc::new(token),
    };
    let app = Router::new()
        .route("/health", get(health))
        .route("/mcp", post(mcp))
        .layer(DefaultBodyLimit::max(65536))
        .with_state(state);
    let port = env::var("PORT").unwrap_or_else(|_| "8080".into());
    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{port}"))
        .await
        .unwrap();
    axum::serve(listener, app).await.unwrap();
}
