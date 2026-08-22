use std::convert::Infallible;

use axum::{
    body::Body,
    extract::OptionalFromRequestParts,
    http::{request::Parts, Request, StatusCode},
    routing::get,
    Router,
};
use axum_extra::TypedHeader;
use headers::ContentType;
use tower::ServiceExt;

struct ContractProbe;

impl<S> OptionalFromRequestParts<S> for ContractProbe
where
    S: Send + Sync,
{
    type Rejection = Infallible;

    async fn from_request_parts(
        _parts: &mut Parts,
        _state: &S,
    ) -> Result<Option<Self>, Self::Rejection> {
        Ok(None)
    }
}

fn require_typed_header_contract<T: OptionalFromRequestParts<()>>() {}

async fn contract_handler(_: Option<ContractProbe>) {}

async fn typed_header_handler(_: Option<TypedHeader<ContentType>>) -> StatusCode {
    StatusCode::NO_CONTENT
}

#[tokio::test]
async fn decisiontrace_optional_typed_header_behavior() {
    require_typed_header_contract::<TypedHeader<ContentType>>();
    let _contract_router = Router::<()>::new().route("/contract", get(contract_handler));

    let app = Router::new().route("/", get(typed_header_handler));
    let absent = app
        .clone()
        .oneshot(Request::builder().uri("/").body(Body::empty()).unwrap())
        .await
        .unwrap();
    let malformed = app
        .oneshot(
            Request::builder()
                .uri("/")
                .header("content-type", "not-a-mime")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    println!("DECISIONTRACE_ABSENT_STATUS={}", absent.status().as_u16());
    println!(
        "DECISIONTRACE_MALFORMED_STATUS={}",
        malformed.status().as_u16()
    );
    assert_eq!(absent.status(), StatusCode::NO_CONTENT);
    assert!(matches!(
        malformed.status(),
        StatusCode::BAD_REQUEST | StatusCode::NO_CONTENT
    ));
}
