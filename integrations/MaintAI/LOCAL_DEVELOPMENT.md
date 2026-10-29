# App owner handoff cho local GitOps

Source ứng dụng không cần đổi deployment thành một service mới. Giữ Dockerfile và entrypoint thật trong app; infrastructure build/import chúng, GitOps quản lý release local. Đọc ../../docs/LOCAL_DEVELOPMENT.md.

Khi chuyển tài liệu app: thay hướng dẫn active MaintAI-k3d bằng Maint-infrastructure/local/README.md và MaintAI-gitops/docs/LOCAL_DEVELOPMENT.md; giữ rõ các test profiles/adapters local và production/shared handoff chưa hoàn tất. Không commit dataset, CA key, token hoặc credentials từ .local. Không coi image/Argo health là benchmark hay full E2E.

Entrypoints M5 đã khóa trong config/local/runtime-catalog.json. Thay interface phải cập nhật catalog/source hash sau review; không sửa schema hoặc tạo callback success giả. ML/RAG/training owners cung cấp image/model/config thật; MLflow server vẫn dùng app-owned packaging.
