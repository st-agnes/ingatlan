# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY backend/Otthonra.Api/Otthonra.Api.csproj backend/Otthonra.Api/
# proxy_ca is optional outside managed workspaces; never copied into an image layer.
RUN --mount=type=secret,id=proxy_ca \
    if [ -s /run/secrets/proxy_ca ]; then SSL_CERT_FILE=/run/secrets/proxy_ca dotnet restore backend/Otthonra.Api/Otthonra.Api.csproj; else dotnet restore backend/Otthonra.Api/Otthonra.Api.csproj; fi
COPY backend/Otthonra.Api/ backend/Otthonra.Api/
COPY dist/data/settlements.json dist/data/settlements.json
RUN dotnet publish backend/Otthonra.Api/Otthonra.Api.csproj -c Release -o /app --no-restore
FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /app .
COPY dist/THIRD-PARTY-NOTICES.txt /app/THIRD-PARTY-NOTICES.txt
ENV ASPNETCORE_HTTP_PORTS=8080
USER $APP_UID
EXPOSE 8080
ENTRYPOINT ["dotnet", "Otthonra.Api.dll"]
