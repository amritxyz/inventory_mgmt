const btn = document.getElementById("sort_btn");

if (btn) {
    btn.addEventListener("click", function(e) {
        e.preventDefault();

        const sortInput = document.getElementById("sort_input");
        sortInput.value = sortInput.value === "desc" ? "asc" : "desc";

        sortInput.form.submit();
    });
}
